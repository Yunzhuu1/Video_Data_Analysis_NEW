# lineage-aware-planning Specification

## Purpose
TBD - created by archiving change lineage-aware-planning. Update Purpose after archive.
## Requirements
### Requirement: 版本化最小血缘目录
系统 SHALL 以单一 Git 版本化 JSON 资源描述 MVP table grain、metric path、dimension binding 与有向 join edge；Spring SHALL 使用 `schema.sql` 的表列注册表校验所有物理引用，并把 lineage overlay、compiler 所需规范化 metric definitions 与 schema projection 冻结为包含组合 `catalogVersion` 及三个子 hash 的不可变内部 snapshot。Python real 模式 SHALL 仅经平台 API 消费，mock 模式 SHALL 读取同一资源语义而非复制目录；同一 run 的 Compiler SHALL 只读冻结 snapshot。

#### Scenario: Catalog 引用合法
- **WHEN** `lineage_catalog.json` 中所有 metric/path/binding/edge ID 唯一且引用的 metric、table、column 均存在
- **THEN** Spring 加载成功并由 `/internal/lineage/snapshot` 返回稳定 catalogVersion、lineageHash、metricCatalogHash、schemaHash 与完整冻结 snapshot

#### Scenario: Catalog 引用未知字段
- **WHEN** 某 path、binding 或 join edge 引用 `schema.sql` 不存在的表或字段
- **THEN** catalog 校验 fail-fast，错误包含具体 ID/表/字段，禁止向 Agent 发布部分有效 snapshot

#### Scenario: Metric 定义变化使版本失效
- **WHEN** lineage overlay 不变但某指标的公式、event filter、source 或 time field 发生变化
- **THEN** metricCatalogHash、组合 catalogVersion 与基于它生成的 planId 均变化，旧 plan 不得在新 snapshot 下通过验证

#### Scenario: Mock 与 real 跨语言 hash 一致
- **WHEN** Java 与 Python 按项目 canonical JSON profile 处理同一固定 fixture 及同一提交的组合 snapshot
- **THEN** canonical bytes 与小写 SHA-256 完全一致，且 catalogVersion、三个子 hash、path/binding/edge ID 集合一致

### Requirement: 单指标合法计划枚举
`PlanEnumerator` SHALL 对单指标 aggregate/trend/ranking ResolvedIntent 枚举最多 5 个完整 CandidateQueryPlan；每个计划 SHALL 以 `fieldRoutes` 保存 dimensions、filters、ordering、time filter/time bucket 的全部物理路径。JOIN edge 的 `from` SHALL 表示指标行侧、`to` SHALL 表示维度查找侧，cardinality SHALL 从 from 看向 to；Enumerator 只可从 metric source 沿 N:1/1:1 edge 正向扩展且最多两跳。候选 SHALL 覆盖请求的每个字段用途并可由当前 compiler 编译；反向 edge、1:N、N:N、未知 cardinality、detail、多指标及未覆盖组合 SHALL 不进入候选而保留结构化 rejected reason。

#### Scenario: 直接维度路径
- **WHEN** `total_likes + creator` 可由 `user_behavior_fact.creator_id` 直接绑定
- **THEN** 候选包含 fact metricPath、creator binding、0 条 JOIN edge 且 legality evidence 全部 PASS

#### Scenario: 两跳维度路径
- **WHEN** `completion_rate + creator name` 需要 `play_detail → content_dim → creator_dim`
- **THEN** 候选包含稳定的 play-content/content-creator edge ID，joinCount=2，且不生成不存在的 `play_detail.creator` 字段

#### Scenario: 无 GROUP BY 但过滤需要 JOIN
- **WHEN** ResolvedIntent 表示“美食类视频的完播率”，`dimensions=[]` 且 `filters` 包含 `category=美食`
- **THEN** 候选 fieldRoutes 包含 `category/FILTER` 的 binding 与 `play_detail → content_dim` edge，Compiler 无需且不得重新 BFS

#### Scenario: 拒绝聚合 fan-out
- **WHEN** 某预聚合 path 只能沿 1:N 方向扩展到请求维度（如 category 聚合向 content/creator 分摊）
- **THEN** 该 path 以 `UNSAFE_JOIN_CARDINALITY` 被拒绝，不得进入 CandidateQueryPlans

#### Scenario: 拒绝反向遍历安全边
- **WHEN** 某请求只能把已声明的 `metric-row → dimension` N:1 edge 反向解释为 `dimension → metric-row`
- **THEN** Enumerator 以 `REVERSE_JOIN_NOT_ALLOWED` 拒绝该路径，不得因原 edge 正向安全而接受反向 fan-out

#### Scenario: 非 MVP 请求走兼容路径
- **WHEN** ResolvedIntent 为 detail、包含多个指标、需要三跳或无合法 binding
- **THEN** Enumerator 返回零候选和明确 reason，设置 legacy planning fallback，不自行生成近似计划

### Requirement: 条件式受约束 Planner Agent
系统 SHALL 仅在多个合法候选存在不可由支配规则消除的 cost/freshness 取舍时调用独立 `QueryPlannerAgent`；0 个候选走 legacy、1 个候选自动选择、被同 freshness 下更低成本/更少 JOIN 候选支配的计划由确定性策略排除。Planner SHALL 只从本轮候选复制 `selected_plan_id` 并返回枚举 reason code/explanation/confidence，不得修改 ResolvedIntent 或输出/创造 table、column、join、SQL、path ID。

#### Scenario: 单候选自动选择
- **WHEN** Enumerator 只返回一个合法计划
- **THEN** `selectionSource=AUTO_SINGLE`，不调用 Planner LLM，selectedPlanId 为该候选

#### Scenario: 普通与实时路径取舍
- **WHEN** daily 低成本/T+1 与 fact 高成本/REALTIME 均合法且存在真实取舍
- **THEN** 调用 Planner；普通问法按 planning skill 默认偏好低成本，明确“实时/最新”的问法选择 REALTIME，并记录 reasonCode/skillVersion

#### Scenario: Planner 伪造计划 ID
- **WHEN** Planner 返回不在本轮 CandidateQueryPlans 中的 selected_plan_id
- **THEN** Validator 返回 REPLAN/INVALID_PLAN_ID，不得读取 LLM 提供的物理字段或编译 SQL

### Requirement: 计划验证、一次重选与兼容回退
每个 selected plan SHALL 经确定性 `PlanValidator` 使用同一组合 catalog snapshot 重新验证 snapshot 实际内容与 lineage/metric/schema/组合四个声明 hash 的一致性、candidate membership、catalog version、metric 与全部 field usage 完整性、path/binding/edge、JOIN 正向语义/跳数和 compiler 支持；完整性检查 SHALL 先于 selected ID 与 candidate 检查，任一 snapshot 内容/声明缺失、非法或不一致 SHALL 返回 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`，禁止重选和 plan compiler，并进入不读取该 snapshot 的 legacy synthesizer。Enumerator SHALL 将实际 snapshotFingerprint 写入 Candidate 并纳入 planId，Validator PASS SHALL 返回同一 fingerprint。Compiler SHALL 在入口把 JSON snapshot 复制为无外部引用的私有副本，在副本上校验后要求其 fingerprint、Validator PASS fingerprint 与 plan fingerprint 完全一致，再递归冻结并只消费该冻结副本与 selected plan fieldRoutes；不得在校验后读取原始 snapshot、重新 BFS、调用 legacy `_resolve_path()` 覆盖路径或读取更新后的 metric catalog。普通 REPLAN 失败最多重选一次，之后 SHALL 回退现有 legacy synthesizer，legacy 失败才进入 raw SQL fallback。

#### Scenario: 合法计划驱动编译
- **WHEN** snapshot 的实际 lineage、metric definitions、schema projection 分别匹配三个声明 hash 和组合 catalogVersion，selected plan 验证 PASS 且 planning mode=active
- **THEN** SQL compiler 仅按冻结 snapshot 与 plan fieldRoutes 的可信 ID 解析 source/expressionRef/binding/edge，生成可由真实 MySQL 解析执行的确定性 SQL

#### Scenario: 三组件内容漂移优先拒绝
- **WHEN** lineage、metric definitions 或 schema projection 任一实际内容被替换但保留旧的三个子 hash 与 catalogVersion
- **THEN** Validator 在 candidate membership 与重新枚举前返回 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH` 及确定顺序的 mismatchedComponents，不调用 Planner 重选或 plan compiler

#### Scenario: 声明缺失或单独篡改
- **WHEN** 四个声明 hash 任一缺失、不是64位小写hex，或只有声明值变化而实际内容不变
- **THEN** snapshot 同样以 `SNAPSHOT_INTEGRITY_MISMATCH` 拒绝，不把错误降级为 INVALID_PLAN_ID、CANDIDATE_TAMPERED 或普通 NO_CANDIDATE

#### Scenario: 验证后内容再次变化
- **WHEN** Validator 对合法 snapshot 返回 PASS 后、调用 plan compiler 前 snapshot 内容再次被修改
- **THEN** compiler 先复制当前 snapshot、在私有副本上校验并要求副本fingerprint等于Validator PASS fingerprint和plan fingerprint，再递归冻结；即使修改后的S1自身四hash一致，只要不同于Validator验证的S0也必须拒绝；冻结完成后对原snapshot的修改不影响SQL，Compiler全程不得再次读取原对象

#### Scenario: 完整性拒绝走兼容路径
- **WHEN** Enumerator 或 Validator 发现 snapshot 完整性失败
- **THEN** 有序节点路径为 PLAN_ENUMERATE→PLAN_VALIDATE(REJECT)→SQL_SYNTHESIZE(legacy)→SQL_HARD_GUARD，记录 integrity validation code/components、设置 legacyPlannerFallback=true且 planningRetryCount 不增加；不得访问PLAN_SELECT或plan compiler，不得以NO_CANDIDATE覆盖原code，legacy SQL不读取该snapshot并仍经过统一SQL Guard

#### Scenario: 首选计划失败后重选
- **WHEN** 首选计划验证为 REPLAN 且仍有未排除候选
- **THEN** 结构化 validation feedback 返回 Planner，planningRetryCount 增加且最多再选择一次

#### Scenario: 重选耗尽回退
- **WHEN** 第二次选择仍失败或无剩余候选
- **THEN** `legacyPlannerFallback=true` 并调用既有 synthesize；不得无限循环或直接执行未验证计划

#### Scenario: Off 和 Shadow 模式
- **WHEN** `LINEAGE_PLANNING_MODE=off|shadow`
- **THEN** off 不参与规划；shadow 生成完整观测但最终始终使用 legacy SQL，二者均不改变既有业务结果

### Requirement: 规划过程可审计
系统 SHALL 在 state、Run Trace 与 `includeDebug=true` 通道记录组合 catalogVersion、lineage/metric/schema hash、candidate fieldRoutes/rejected plans、selectedPlanId、selectionSource、planner reason/skill version、validation verdict/code、planningRetryCount、lineageEdgeIds、legacyPlannerFallback 与可归因的 Planner 调用成本；默认业务响应 SHALL 不暴露这些内部字段。

#### Scenario: Debug 展示 Planner 决策链
- **WHEN** 请求以 `includeDebug=true` 运行且调用 Planner Agent
- **THEN** debug 可还原候选、选择、理由、验证、边 ID、重试与最终编译来源

#### Scenario: 默认响应契约不变
- **WHEN** 请求未开启 includeDebug
- **THEN** 业务响应不包含 lineage/planner 内部字段，现有 AnalysisReport 契约不变
