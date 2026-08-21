## Context

当前主链路已经把概率性语义解析与确定性 SQL 合成分开：MetricCandidateRetriever 缩小指标候选，`SemanticResolverAgent` 输出逻辑 `ResolvedIntent`，`sql_synthesizer.py` 再生成 SQL。但物理规划仍隐含在 `_resolve_path()`、`_field_expr()`、`_ALIAS` 与多指标分支里：同一指标的 daily/fact 选路、维度跨表 JOIN、eventFilter 与时间字段都靠条件分支。真实代码已存在 `play_detail + creator` 会落到不存在的 `pd.creator`、`video_revenue + category` 会落到不存在的 `vr.category` 等可达缺口。

本 change 是面向秋招展示的收敛垂直切片，不建设完整企业语义平台。目标是在保留现有 N=61/R1 基线和 legacy 合成器的前提下，用最少的新元数据证明：LLM 可以在系统生成的合法动作空间中自主选择物理路径，而不被允许发明表、列和 JOIN。

现有职责边界保持：Spring 是 schema/平台治理权威，Python 是唯一 Agent 编排与 SQL 合成实现，Python 不直连业务库。`schema.sql` 继续是表/列 DDL 唯一源，`metric_catalog.json` 继续是指标定义源；本 change 的 lineage catalog 只补充路径/关系，不复制业务数据。

## Goals / Non-Goals

**Goals:**

- 用版本化 JSON 显式描述 MVP 表粒度、指标物理路径、维度绑定、JOIN 边、freshness/cost，并在启动/读取时校验表列引用。
- 在 `ResolvedIntent` 后引入独立、条件调用的 `QueryPlannerAgent`；Semantic Agent 负责“查什么”，Planner 负责“合法候选中选哪条”。
- 确定性枚举最多两跳、仅 N:1/1:1 安全方向的单指标候选计划；LLM 只复制 `plan_id`，计划验证后再编译。
- 解锁 `completion_rate + creator`、`video_revenue + category` 等旧硬编码不稳定路径，并演示 `total_likes + category` 的 daily/fact 成本-新鲜度取舍。
- 全量记录 catalog、候选、选择来源、reason、validation、retry、edge 与 legacy fallback，为审计和未来 Skill Candidate 提供事实数据。
- 建立独立 path golden 与分层评测，隔离 Semantic LLM 方差并保持 N=61/R1 回归。

**Non-Goals:**

- 不引入图数据库、MySQL 血缘表、元数据管理后台或 catalog 发布平台。
- 不定义完整表达式 AST/DSL，不迁移全部 15 个指标，不删除现有 metric catalog 字段。
- 不实现多指标血缘规划、跨子计划 HAVING、key-spine merge、detail intent 或任意多跳/成本优化器。
- 不允许 Planner 修改 ResolvedIntent，不做 Planner → Semantic 的反向重解析。
- 不自动提取、修改或发布 Skill；本轮只记录 `plannerSkillVersion` 与可供未来离线挖掘的审计数据。
- 不修改 SQL Guard、HITL、安全策略或前端。

## Decisions

### D1：三种信息严格分层，lineage 使用 Git 版本化 JSON overlay

物理表列继续来自 `schema.sql → TableSchemaRegistry`；指标名称/公式继续来自 `metric_catalog.json` / `/internal/metrics`；新增 `src/main/resources/lineage_catalog.json` 只描述：

- `tables`: `tableName`、`grain`；
- `metricPaths`: 稳定 `pathId`、`metricCode`、`sourceTable`、`expressionRef=primary|fact`、`eventFilterRef`、`timeFieldRef`、`nativeDimensions`、`supportedIntents`、`freshness`、`costTier`；
- `dimensions` / `dimensionBindings`: 逻辑维度在具体表上的 key/label 字段；
- `joinEdges`: 稳定 `edgeId`、`fromTable/fromColumns`、`toTable/toColumns`、`cardinalityFromTo=N:1|1:1`。`from` 固定表示当前指标行侧，`to` 固定表示被连接的维度查找侧，cardinality 始终从 from 看向 to；Enumerator 只能正向遍历该边。若业务需要反向路径，必须另建一条能够独立证明安全的有向边，禁止把现有边隐式反转。

Spring `LineageCatalogService` 用 Jackson 加载，复用 `TableSchemaRegistry` 校验所有表列、ID 唯一性和引用完整性。发布给单次 run 的不可变 `CatalogSnapshot` 不仅包含 lineage overlay，还冻结当前 compiler 实际使用的规范化 metric definitions（公式、source、fact formula/event filter、time field 等）与最小 schema projection（表及字段集合）。Compiler 不得在同一 run 内另行读取可变 metric catalog。`catalogVersion` 是该三部分组合对象的 SHA-256；同时保留 `lineageHash`、`metricCatalogHash`、`schemaHash` 便于定位漂移。`planId` 必须纳入组合 catalogVersion，因此 metric 公式或 schema 变化都会产生新版本/新 plan ID。

跨 Java/Python 的 hash 使用项目固定 canonical JSON profile，而不是依赖各语言默认序列化：对象 key 按 Unicode code point 升序；数组保留语义顺序，但 catalog 中语义无序的集合必须先按稳定 ID/code 排序；字符串为 UTF-8、保留非 ASCII 字符，仅对 JSON 必须字符和控制字符转义；boolean/null 使用小写字面量；仅允许有符号 64 位整数并以无前导零十进制表示（`-0` 归一为 `0`），禁止 float/NaN/Infinity 进入版本对象。三部分放入固定 key 的组合对象后 canonical serialize，再计算小写十六进制 SHA-256。仓库提供一份包含中文、转义、null、数组和整数边界的 fixture 及唯一 expected hash，Java/Python 必须对同一 fixture 断言字节与 hash 一致。

Spring 通过只读 `/internal/lineage/snapshot` 返回上述完整快照。real Python 只经平台 API 获取；mock Python 读取同一仓库资源、构造等价 metric/schema projection 并运行等价结构与 fixture hash 校验，不复制第二份 lineage catalog。

选择 JSON 而非 MySQL/图数据库，是因为当前 7 表/4 指标垂直切片无需动态元数据服务；Git review、版本回放和 mock 可复现的收益更高。选择 overlay 而非完整表达式 DSL，是为了复用当前已验证的 `formula/factFormula/factEventFilter/timeField`，`expressionRef` 只决定引用哪套定义，避免本 change 变成 SQL 编译器重写。

### D2：PlanEnumerator 生成完整合法计划，而不是把任意边交给 LLM 拼装

输入为原始 question、不可变 catalog snapshot 和 `ResolvedIntent`。MVP 仅在 `len(metrics)==1` 且 intent∈{aggregate,trend,ranking} 时工作：

1. 根据 metric code 取 active MetricPath；
2. 从 `dimensions`、`filters`、`ordering`、`time_range/granularity` 汇总所有需要落到物理字段的 semantic fields，并标注用途；指标值 filter/order 绑定 metric expression，逻辑维度 filter/order/group 绑定 dimension binding，时间范围/粒度绑定该 metric path 的 time field；
3. 对每个物理字段优先找源表直接 binding，否则从 metricPath.sourceTable 出发，在 JoinEdge 上稳定 BFS，最大两跳；
4. BFS 只允许沿 edge 的 `from → to` 正向移动，且 `cardinalityFromTo` 必须为 N:1 或 1:1；反向、1:N、N:N 与未知 cardinality 一律拒绝，防聚合 fan-out；
5. 检查 path 支持 intent、每个 semantic field 的用途均有唯一可编译 route、所有逻辑字段被保留、当前 compiler 支持该组合；
6. 生成完整 `CandidateQueryPlan`，按 path/edge/binding ID canonical 排序去重，最多 5 个；同时保留 rejected reason codes。

`CandidateQueryPlan` 至少包含：`planId`（canonical plan + 组合 catalogVersion 的 SHA-256 短 hash）、`metricPathId`、`fieldRoutes[{semanticField, usages, routeKind, bindingId?, metricPathId?, edgeIds}]`、`sourceTable`、`freshness`、`costTier`、`joinCount`、`catalogVersion` 和 legality evidence。`usages` 至少覆盖 `GROUP_BY|FILTER|ORDERING|TIME_FILTER|TIME_BUCKET`，`routeKind` 至少区分 `DIMENSION_BINDING|METRIC_EXPRESSION|TIME_FIELD`；同一字段可合并多个 usage，但不得省略任何实际用途。LLM 不得构造这些字段。

例如“美食类视频的完播率”即使 `dimensions=[]`，也必须在 plan 中保存 `category/FILTER` 的 route 与 `play_detail → content_dim` edge；Compiler 不得为了生成 WHERE 再自行 BFS。Validator 和 Compiler 都只接受 selected plan 中已冻结的 `fieldRoutes`，避免“Planner 选 A、Compiler 实际走 B”。

本轮不实现通用 grain algebra；安全性由“显式 path 支持的逻辑维度 + N:1/1:1 安全 JOIN + 单指标”共同约束。`table.grain` 用于审计和基本一致性检查，不据此声称已支持 ratio/count-distinct 任意 rollup。

### D3：Planner Agent 与 Semantic Agent 分开，且只有存在真实取舍时调用

`SemanticResolverAgent` 输出逻辑 `ResolvedIntent`，不接收 table/join/cost；用户明确说“创作者”时必须保留 `creator`，不能因为指标的 native dimensions 没列出而删除。metric prompt 中 dimensions 只作为原生能力提示，不是逻辑抽取白名单；全局逻辑维度仍是输出权威。

枚举后路由：

- 0 个候选：`selectionSource=LEGACY_FALLBACK`，不调用 Planner；
- 1 个候选：`AUTO_SINGLE`；
- 多候选且一个在 freshness 相同下被 cost/join Pareto 支配：`AUTO_POLICY` 选非支配计划；
- 多候选存在成本/新鲜度真实取舍：调用 `QueryPlannerAgent`。

Planner 使用独立 `query-planning-v1` system skill，输入原问题、只读 ResolvedIntent、候选摘要和上次 validation feedback；输出严格 JSON：`selected_plan_id`、枚举 reason code、自由文本 explanation、confidence。它不得修改 intent、输出 SQL/表/列/JOIN，且 selected ID 必须来自本轮候选。普通“各分类点赞量”默认 skill 偏好低成本 daily；明确“实时/最新”等语义时选择 realtime fact。这里的偏好由 Planner 解释，不把关键词规则硬编码进 Enumerator。

同一模型可以承担两个 Agent，但 Prompt、调用、token/latency 和版本独立计量；分开调用便于隔离评测。只有 AUTO 分支时没有第二次 LLM 成本，避免“为 Agent 而 Agent”。

### D4：PlanValidator 是选择后的确定性裁决，最多重选一次

Validator 基于当前 run 持有的同一组合 catalog snapshot 重算：catalog version、plan/candidate membership、metric 与全部 field usage 完整性、path/edge/binding 有效性、JOIN 正向语义、最大跳数、compiler 支持。它必须拒绝缺失 filter/ordering/time route、route usage 不匹配、edge 反向使用或 snapshot/plan 版本不一致的计划。裁决：

- `PASS`: 进入计划驱动编译；
- `REPLAN`: 排除失败 planId，把结构化 `code/reason/suggestion` 返回 Planner；最多一次；
- `UNSUPPORTED`: 或第二次失败，走 legacy。

第一版不返回 `RE_RESOLVE`，防 Semantic/Planner 循环扩大。Planner 伪造 ID直接 `REPLAN`，不得用 LLM输出的 table/column 兜底。run 固定完整 snapshot（lineage + metric definitions + schema projection）；若实现发现平台版本变化，当前 run 继续使用已持有版本，下一 run 才读取新版本。

### D5：计划驱动编译是 legacy 合成器的窄入口，不重写多指标逻辑

新增单指标计划编译入口，从 run 冻结 snapshot 和 selected plan 的稳定 ID重新解析可信物理字段：

- metric expression/event filter/time field 通过 `expressionRef` 读取 snapshot 内冻结的 metric definition，禁止回读运行时 metric catalog；
- source、dimension/filter/ordering/time binding 和 JOIN clauses 仅来自 selected plan 的 `fieldRoutes` 与其引用的 catalog ID；Compiler 禁止再次调用 BFS 或 `_resolve_path()` 覆盖选择；
- WHERE/HAVING/time/group/order 继续复用现有确定性格式化逻辑。

`SQL_SYNTHESIZE` 的优先级：active + validated plan → plan compile；shadow/off、无候选、验证失败、非 MVP（多指标/detail）→ 现有 `synthesize()`；legacy 也失败 → raw LLM SQL。`sql_source` 继续表示 semantic/fallback/memory，另用 `planSelectionSource/legacyPlannerFallback` 表示物理规划来源，禁止混用。

新增 `LINEAGE_PLANNING_MODE=off|shadow|active`：off 完全旧行为；shadow 枚举/观测但始终 legacy 编译，用于校准；active 才让 validated plan 驱动 SQL。该开关是回滚手段，不改变业务 API 默认契约。

### D6：主图显式增加规划节点，但外部接口不变

主图演进为：

```text
ROUTER → SCHEMA → SEMANTIC_RESOLVE
  → PLAN_ENUMERATE
    → [AUTO] PLAN_VALIDATE
    → [TRADEOFF] PLAN_SELECT → PLAN_VALIDATE
      → [REPLAN once] PLAN_SELECT
  → SQL_SYNTHESIZE（plan compile 或 legacy）
  → SQL_HARD_GUARD → SQL_EXECUTE → SQL_SOFT_DQ → ANSWER
```

可以用独立 LangGraph 节点实现，Planner 未调用时跳过 `PLAN_SELECT`。审批恢复和 checkpoint 不变；规划发生在 SQL 产生前，不改变已审批 SQL 不漂移不变式。

### D7：观测和评测按 Semantic / Planning / Result 三层隔离

state/debug/Java debug 通道新增：组合 catalogVersion、lineage/metric/schema hashes、candidatePlans（ID+fieldRoutes+软属性+合法证据摘要）、rejected reasons、selectedPlanId、selectionSource、plannerReasonCode、plannerSkillVersion、validation verdict/code、planningRetryCount、lineageEdgeIds、legacyPlannerFallback、planner tokens/latency。默认 `includeDebug=false` 的业务响应不变；Run Trace 节点记录完整输入输出。

新增 `lineage_cases.yaml`（8~10 条），golden path 由人工依据 DDL/业务口径独立标注，不由 Enumerator 反向生成。三层评测：

- 固定 ResolvedIntent → Enumerator：Path Recall（golden plan/path 是否在候选）；
- 固定候选/Planner：Plan Selection Accuracy、非法 ID 拒绝、Replan Success；
- 端到端：N=61 L1-L4/ERROR/sql_source，R1 保持 29/29，并单列规划调用率、legacy fallback、token/latency。

普通/实时两条真实 Planner LLM 用例只作为单轮方向性观测；确定性硬门槛是 path cases 全覆盖、非法计划拒绝 100%、off 模式零回退、active 下既有 N=61/R1 不回退。embedding 与 memory 均关闭以隔离变量。

## Risks / Trade-offs

- [Risk] `lineage_catalog.json` 与 `schema.sql`/metric catalog 漂移 → Spring fail-fast 校验并冻结 lineage/metric/schema 组合 snapshot；planId 纳入组合版本；mock/real 以固定 canonical fixture 校验跨语言 hash，报告三个子 hash 与组合版本。
- [Risk] Planner 选择的路径在 Compiler 中被重新推导而漂移 → CandidateQueryPlan 保存 dimension/filter/ordering/time 全部 fieldRoutes，Validator/Compiler 禁止自行 BFS 或读取 plan 外物理绑定。
- [Risk] JOIN edge 方向被误解而接受反向 fan-out → catalog 字段固定 from=指标行侧、to=维度侧、cardinalityFromTo；Enumerator 只遍历 outgoing 安全边，并以反向拒绝用例作为硬测试。
- [Risk] 声明 N:1 但数据库未建 FK/UNIQUE，cardinality 只是业务承诺 → MVP 仅登记已知稳定主键路径并在设计/报告标注“catalog-declared”；不宣称自动发现完整血缘。
- [Risk] Semantic Prompt 的 native dimensions 影响 creator 等逻辑维度抽取 → 增加明确契约与端到端用例，维度可执行性留给 Planner。
- [Risk] 第二次 Planner LLM 增加 token/延迟与方差 → 只有多候选真实取舍才调用；独立计量；off/shadow/legacy 可回滚。
- [Risk] Planner 选择不存在的 plan 或被 prompt injection 诱导输出 SQL → 严格 JSON、candidate membership 校验、Validator 重算、非法 ID 100% 拒绝，SQL仍过统一门禁。
- [Risk] 窄计划编译器和 legacy 产生不同 SQL → shadow 逐例 diff、固定 intent compiler tests 与 R1；active 仅在覆盖用例全绿后开启。
- [Risk] 单指标/两跳 MVP 被误读为完整语义层 → proposal/spec/report 固定 Non-Goals、覆盖指标和原始分母，简历只陈述“血缘感知规划 MVP”。
- [Trade-off] 没有完整 grain/聚合代数，不能安全推广到任意多指标 → 本轮宁可 legacy fallback；后续只有在真实查询缺口和 R1 证据出现时再扩展。

## Migration Plan

1. 新增 catalog JSON、Java/Python loader 与纯校验测试，模式默认 `off`，确保现有行为不变。
2. 实现 Enumerator/Validator 与固定 intent path cases，先达到 deterministic hard gates。
3. 实现 plan compiler 并以 `shadow` 对照 legacy SQL/R1，不改变线上选择。
4. 接入 Planner Agent、debug/Run Trace 和一次重选；只在人工构造 tradeoff cases 调真实 LLM。
5. 切 `active` 跑 N=61/R1 全量；如回退，配置切回 `off` 即恢复旧路径，catalog 文件和新增字段可保留。
6. 合并后保留 legacy synthesizer；本 change 不执行删除迁移。

## Open Questions

- 第一版默认配置在合并时为 `active` 还是 `shadow`？倾向：评测门槛全部通过后设 `active`，生产演示可用 `off` 一键回滚。
- `creator` 展示默认使用 ID 还是 name？倾向：逻辑维度默认 key（保证稳定粒度），仅用户明确要求名称时走两跳 label binding；该细节可在 apply 以 path case 固化。
- Planner provider usage 能否精确分离语义与规划 token？若当前 meter 只能总计，需为 Planner 调用前后做快照；无法可靠归因时只报告 prompt chars/latency，不包装总 token。
