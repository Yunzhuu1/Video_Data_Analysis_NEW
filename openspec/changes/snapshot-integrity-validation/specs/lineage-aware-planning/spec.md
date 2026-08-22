## MODIFIED Requirements

### Requirement: 计划验证、一次重选与兼容回退
每个 selected plan SHALL 经确定性 `PlanValidator` 使用同一组合 catalog snapshot 重新验证 snapshot 实际内容与 lineage/metric/schema/组合四个声明 hash 的一致性、candidate membership、catalog version、metric 与全部 field usage 完整性、path/binding/edge、JOIN 正向语义/跳数和 compiler 支持；完整性检查 SHALL 先于 selected ID 与 candidate 检查，任一 snapshot 内容/声明缺失、非法或不一致 SHALL 返回 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`，禁止重选和 plan compiler，并进入不读取该 snapshot 的 legacy synthesizer。普通候选错误验证 PASS 才能计划驱动编译；Compiler SHALL 只消费 selected plan 的 fieldRoutes 与冻结 metric definitions，不得重新 BFS、调用 legacy `_resolve_path()` 覆盖路径或读取更新后的 metric catalog，并 SHALL 在解析任何 snapshot ID 前重复完整性检查以阻断验证后篡改。普通 REPLAN 失败最多重选一次，之后 SHALL 回退现有 legacy synthesizer，legacy 失败才进入 raw SQL fallback。

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
- **THEN** compiler 在解析任何 path/binding/edge/metric definition 前独立拒绝且不生成部分 SQL，Graph 按既有可观测 SynthesisError 降级

#### Scenario: 完整性拒绝走兼容路径
- **WHEN** Enumerator 或 Validator 发现 snapshot 完整性失败
- **THEN** 记录 integrity validation code/components、设置 legacyPlannerFallback=true且 planningRetryCount 不增加，legacy SQL 不读取该 snapshot并仍经过统一 SQL Guard

#### Scenario: 首选计划失败后重选
- **WHEN** 首选计划验证为普通 REPLAN 且仍有未排除候选
- **THEN** 结构化 validation feedback 返回 Planner，planningRetryCount 增加且最多再选择一次

#### Scenario: 重选耗尽回退
- **WHEN** 第二次选择仍失败或无剩余候选
- **THEN** `legacyPlannerFallback=true` 并调用既有 synthesize；不得无限循环或直接执行未验证计划

#### Scenario: Off 和 Shadow 模式
- **WHEN** `LINEAGE_PLANNING_MODE=off|shadow`
- **THEN** off 不参与规划；shadow 生成完整观测但最终始终使用 legacy SQL，二者均不改变既有业务结果
