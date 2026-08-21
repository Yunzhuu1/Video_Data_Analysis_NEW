## MODIFIED Requirements

### Requirement: LLM 只做语义匹配，不写 SQL
`SEMANTIC_RESOLVE` 节点 SHALL 输出结构化 `ResolvedIntent`（指标/维度/时间范围/过滤/排序），不得直接产出 SQL。维度抽取 SHALL 遵循：`date` 属于时间粒度而非业务维度；"各分类/按分类"类问法 → `dimensions`；"X 类视频"类限定 → `filters`。Semantic Agent SHALL 忠实保留用户明确表达的逻辑维度，不得因指标目录只列出原生表维度而静默删除；该维度是否存在可执行物理路径由后续 lineage planner 判定。

#### Scenario: 解析输出结构化意图
- **WHEN** 用户问题进入 `SEMANTIC_RESOLVE`
- **THEN** 节点输出 `ResolvedIntent`（含 `intent`、`metrics`、`dimensions`、`time_range`、`filters`、`ordering`），state 中不出现新 SQL

#### Scenario: date 不入 dimensions
- **WHEN** 用户问题为时间序列类（如"最近7天每天播放量"）
- **THEN** `dimensions` 不含 `date`；时间粒度表达在 `time_range.granularity`

#### Scenario: 各分类归维度
- **WHEN** 用户问题含"各分类/按分类/每类"且讨论指标
- **THEN** `dimensions` 包含对应分类维度（如 `category`），不放入 `filters`

#### Scenario: 类目限定归过滤
- **WHEN** 用户问题用"X 类视频/美食的"限定单一分类
- **THEN** 该限定放入 `filters`（如 `category=美食`），不放入 `dimensions`

#### Scenario: 多分类对比归维度+过滤
- **WHEN** 用户问题用"对比/比较 A 和 B 分类"对比多个分类
- **THEN** `dimensions` 含 `category` 且 `filters` 含 `category IN (A,B)`（区别于单分类限定的 `filters =`）

#### Scenario: 逻辑维度不受原生路径限制
- **WHEN** 用户问题明确询问“每位创作者的完播率”，而 completion_rate 的原生表维度只列 content
- **THEN** Semantic Agent 仍输出 `dimensions=[creator]`；不得为适配当前表结构改成 content 或删除 creator

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent`、run 内冻结的 metric definitions 与可选的已验证血缘 QueryPlan 确定性合成 SQL；相同 intent + 组合 catalogVersion + selectedPlanId SHALL 生成相同 SQL。planning active 且 QueryPlan 验证 PASS 时，source、dimension/filter/ordering/time 与 JOIN SHALL 仅由可信 fieldRoutes/path/binding/edge ID解析，禁止编译阶段重新 BFS 或读取 plan 外更新后的 metric definition；规划未覆盖、off/shadow 或失败时 SHALL 使用既有 legacy 合成器。合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。合成器 SHALL 支持**同源表多指标聚合**（多个指标经 legacy `_resolve_path` 后落在同一无冲突路径时，单 FROM + 多 SELECT 表达式列，共享 group-by/time/filter），并支持**同粒度冲突多指标**（来源冲突或 eventFilter 冲突且共享维度键时，各指标独立聚合子查询 JOIN）。合成器 SHALL 支持**指标值过滤**（`filters[].field` 为指标 code 时生成 HAVING；维度过滤仍生成 WHERE）。多指标 lineage planning 不属于本 change，多指标继续走 legacy；多指标 ranking/detail、异粒度冲突多指标及“冲突多指标 + 指标值过滤”组合 SHALL 明确降级（SynthesisError → raw SQL）。`time_range.type == "relative"` 时，合成前 SHALL 以**数据末日为锚**展开为 absolute 区间（含端点），合成 SQL 含时间过滤。

#### Scenario: 同意图同 SQL
- **WHEN** 两次输入相同的 `ResolvedIntent`、catalogVersion 与 selectedPlanId（或均走相同 legacy 路径）
- **THEN** 合成器产出完全一致的 SQL 文本

#### Scenario: 合成 SQL 可复验
- **WHEN** 合成器产出 SQL
- **THEN** 该 SQL 可通过 `SQL_HARD_GUARD` 校验（或返回明确校验失败信息）

#### Scenario: 合成 SQL 引用真实表名
- **WHEN** 合成器基于 validated QueryPlan 或 `metric_definition.sourceTable` 合成 SQL
- **THEN** FROM 子句包含真实表名与别名声明（如 `FROM metric_daily md`），且该 SQL 可在真实 MySQL 上解析执行，不得出现未声明别名的 `FROM md`

#### Scenario: 血缘计划驱动单指标合成
- **WHEN** 单指标 aggregate/trend/ranking 请求在 active 模式得到验证 PASS 的 selectedPlanId
- **THEN** source、dimension/filter/ordering/time expression 与 JOIN 仅从 selected fieldRoutes/path/binding/edge 及冻结 metric definitions 解析，禁止再次 BFS 或调用 `_resolve_path` 覆盖 Planner 选择

#### Scenario: 血缘规划未覆盖走 legacy
- **WHEN** 请求为多指标/detail、零候选、规划验证失败或 planning mode=off|shadow
- **THEN** 调用 change 前既有 `synthesize()` 行为；只有 legacy 也抛 SynthesisError 才降级 raw SQL

#### Scenario: 同源表多指标聚合
- **WHEN** ResolvedIntent 的 metrics 经 `_resolve_path` 后全部落在 `metric_daily` 列路径（如 metric_daily 的 total_plays + total_likes），且 intent ∈ {aggregate, trend}、共享同 group-by 集
- **THEN** 合成单 FROM 多 SELECT 列 SQL（每列 `agg_expr AS code`），在真实数据库可解析执行

#### Scenario: 指标值过滤（HAVING）
- **WHEN** ResolvedIntent.filters 含指标 code 字段（如 completion_rate）且 op ∈ {>, >=, <, <=}
- **THEN** 合成 SQL 生成 `HAVING <agg_expr> <op> <value>`，且 agg_expr 复用 SELECT 的同一表达式；维度字段过滤仍走 WHERE

#### Scenario: 冲突多指标（子查询 JOIN）
- **WHEN** 多指标存在来源冲突（不同 sourceTable，如 play_detail + user_behavior_fact）或 eventFilter 冲突（同源 fact 不同 filter，如 play vs like），且共享同一组维度键/时间/过滤
- **THEN** 合成各指标独立聚合子查询并按维度键 JOIN，各子查询保留自身 eventFilter，SQL 可在真实数据库解析执行

#### Scenario: 异粒度冲突多指标降级
- **WHEN** 冲突多指标无法按同一组维度键聚合（粒度不对齐）
- **THEN** 抛 SynthesisError，节点降级 raw SQL 生成（sql_source=fallback），不产出错误 JOIN

#### Scenario: 约束显式失败
- **WHEN** 多指标但 intent 为 ranking/detail，或维度/时间/过滤/排序不一致
- **THEN** 抛 SynthesisError（显式失败优于产出错误 SQL）

#### Scenario: 相对时间展开
- **WHEN** ResolvedIntent 的 time_range 为 relative（如 {amount: 7, unit: "day"}）
- **THEN** 合成前展开为 absolute 区间（锚点=数据末日，含端点：最近7天 = 末日往前 6 天），合成 SQL 含 `WHERE <timeField> BETWEEN start AND end`

#### Scenario: 锚点查询失败降级
- **WHEN** 数据末日锚点查询失败（网络/权限）
- **THEN** 保持 relative（合成器现状），记录 warning 且不打断主链路；R1 侧以 value_mismatch 暴露（不静默）

