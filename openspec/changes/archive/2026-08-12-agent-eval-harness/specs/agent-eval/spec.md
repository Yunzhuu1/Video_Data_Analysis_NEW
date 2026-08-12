## ADDED Requirements

### Requirement: golden_spec 结构化标准答案
每个可判定 golden case SHALL 包含 `golden_spec`（`{intent, metrics, dimensions, time_range, filters, ordering}`），与 agent 的 `ResolvedIntent` 输出同构。

#### Scenario: 用例可判定
- **WHEN** 一个 case 有唯一确定的指标查询意图
- **THEN** 该 case 标注 `golden_spec`，可参与口径正确率统计

#### Scenario: 开放性用例单列
- **WHEN** 一个 case 无法唯一确定意图（开放性/歧义问题）
- **THEN** 该 case 不标注 `golden_spec`，仅统计端到端成功率，不计入口径正确率

### Requirement: 确定性比较器
评测 SHALL 使用确定性 `SpecComparator` 比较 agent 输出与 `golden_spec`：先归一化（指标别名、维度集合、时间区间展开、过滤三元组），再按四层评分输出。

#### Scenario: 时间范围容差
- **WHEN** agent 输出与 golden 的时间区间起点终点相同且长度差 ≤ 1 天、粒度一致
- **THEN** 该字段判定为正确

#### Scenario: 多约束/漏约束判定
- **WHEN** golden 无时间要求而 agent 加了时间过滤，或 golden 有时间要求而 agent 遗漏
- **THEN** 该字段判定为错误

#### Scenario: 四层评分
- **WHEN** 对一批 case 运行比较器
- **THEN** 输出核心口径正确率、严格全字段正确率、平均字段匹配率、分项正确率四项指标

### Requirement: FakeLLM 录制回放
评测与测试 SHALL 支持通过 FakeLLM 离线回放真实 LLM 响应（cassette），不依赖 API key 且结果可复现；未命中时 SHALL 明确报错提示重新录制。

#### Scenario: 回放确定性
- **WHEN** 两次运行同一回放评测
- **THEN** 两次结果完全一致

#### Scenario: 未命中提示
- **WHEN** 请求未命中 cassette（如 prompt 已变更）
- **THEN** 评测失败并提示重新录制，而不是静默通过

#### Scenario: 注入错误响应
- **WHEN** 手工构造 cassette 返回空 SQL/坏 JSON/retryable 错误
- **THEN** 可确定性覆盖重试、fallback、审批分支测试

### Requirement: 真实指标报告与基线对比
评测 SHALL 输出真实数字报告（`docs/eval-report.md`），并支持两个配置的 A/B 对比（逐指标 diff）。

#### Scenario: 报告含实测指标
- **WHEN** 运行真实评测
- **THEN** 报告包含口径正确率、端到端成功率、自动修复成功率、高风险拦截率、单次成本、p50/p95 延迟的实测值

#### Scenario: A/B 对比
- **WHEN** 对同一 golden set 运行两个配置
- **THEN** 报告输出每个指标的基线/新值/差值

### Requirement: 回归门禁
CI SHALL 运行 `pytest` + mock eval（回放模式）作为回归门禁，任何一次改动导致回放评测失败或指标回退 SHALL 阻断合并。

#### Scenario: 回归阻断
- **WHEN** 改动后回放评测失败或核心指标低于基线
- **THEN** CI 失败，阻止合并
