# Agent 评测体系

## Purpose

基于 golden_spec 的评测体系：确定性比较器、FakeLLM 录制回放、真实指标报告与 A/B 对比、回归门禁。

## Requirements

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

### Requirement: 真实模式观测完整性
真实模式评测（platform=real）SHALL 观测等待审批状态、语义解析结果与 SQL 来源，使报告如实反映系统行为，且不得因等待审批路径丢失观测数据。

#### Scenario: 等待审批状态可见
- **WHEN** 引擎对某用例返回 WAITING_APPROVAL
- **THEN** 该用例评测结果记录 status=WAITING_APPROVAL，且与平台运行记录（agent_run）一致

#### Scenario: 等待审批用例的语义结果可见
- **WHEN** 用例触发等待审批且语义解析成功
- **THEN** 评测仍能取得该用例的 resolvedIntent 并参与口径正确率统计，而非按未解析计 0 分

#### Scenario: 报告含 SQL 来源
- **WHEN** 运行真实模式评测
- **THEN** 报告 Source 列展示语义合成或降级来源（semantic/fallback），而非恒为 "-"

### Requirement: 观测数据透传（debug 通道）

评测 SHALL 能获取真实链路的语义解析观测数据（`resolvedIntent` / `sqlRetryCount`）。`/api/agent/analyze` SHALL 提供 `includeDebug` 参数（默认 `false`）；仅在显式开启时 SHALL 将观测数据放入响应的 `debug` 字段，默认关闭时响应 MUST 与现有业务契约完全一致。

#### Scenario: 默认契约不变
- **WHEN** 调用 `/api/agent/analyze` 且未传 `includeDebug`
- **THEN** 响应结构与现有业务契约一致，且不含评测观测数据

#### Scenario: 显式开启返回观测数据
- **WHEN** 调用 `/api/agent/analyze` 且 `includeDebug=true`
- **THEN** 响应 `debug` 字段包含 `resolvedIntent` 与 `sqlRetryCount`

#### Scenario: runner 基于真实观测数据判分
- **WHEN** eval runner 以 `includeDebug=true` 运行 real 评测
- **THEN** L1~L4 依据响应中真实的 `resolvedIntent` 计算，而非空白判 0 分

### Requirement: 评测失败隔离

评测运行器 SHALL 逐用例隔离执行。环境性失败（网络/超时/限流/5xx）SHALL 标记为 `ERROR`，不计入 `judged` 与口径正确率分母，并在报告中单列；任何单条用例失败 MUST NOT 中断整场评测。

#### Scenario: 环境失败不中断整场
- **WHEN** 某条用例发生网络超时或限流
- **THEN** 该用例标记为 `ERROR`，其余用例继续评测

#### Scenario: ERROR 不计入口径分母
- **WHEN** 聚合评测指标时存在 `ERROR` 用例
- **THEN** `ERROR` 用例不计入 `judged`，报告显示「评测可用性 x/21」

#### Scenario: real 模式重试退避
- **WHEN** real 评测遇到可重试的环境错误（如限流）
- **THEN** 重试一次并退避，仍失败才标记 `ERROR`

### Requirement: 正交运行轴

评测运行器 SHALL 以两个正交参数控制运行方式：`--llm <mock|record|replay|real>` 与 `--platform <mock|real>`，替代单一 `--mode`。SHALL 支持"真实 LLM + mock 平台"的语义层评测组合（无 MySQL 也能产出 L1~L4）。报告 SHALL 自描述运行配置，只有配置一致的报告 SHALL 允许 A/B 对比。

#### Scenario: 语义层评测
- **WHEN** 以 `--llm real --platform mock` 运行评测
- **THEN** 使用真实 LLM 与本地 mock 平台，产出 L1~L4 基线，且不依赖 MySQL

#### Scenario: 报告自描述配置
- **WHEN** 生成评测报告
- **THEN** 报告头部记录 `llm_source` / `platform_source` / `model` / `eval_date`

#### Scenario: A/B 配置一致性校验
- **WHEN** 对比两份评测报告
- **THEN** 若两份报告运行配置不一致，拒绝对比并提示原因

### Requirement: mock 数据与真实数据对齐

评测 mock 层 SHALL 与真实种子数据共用同一份指标定义（单数据源），并 SHALL 有测试断言 golden 用例覆盖的指标都在该定义内，防止 mock 与真实漂移。

#### Scenario: mock 与真实同源
- **WHEN** mock 平台返回指标 catalog
- **THEN** 其内容与真实种子数据来自同一份共享定义，指标集合一致

#### Scenario: golden 指标覆盖
- **WHEN** 运行评测前校验
- **THEN** 所有 golden 用例使用的指标均存在于共享定义中，否则测试失败

### Requirement: 基线报告可信

评测报告 SHALL 让关键指标（L1/L2/L3）带分母展示（如 `87% (13/15)`），并 SHALL 单列 `ERROR` 用例明细，保证数字可辩护、可审计。

#### Scenario: 指标带分母
- **WHEN** 报告输出口径核心正确率等指标
- **THEN** 数值同时展示分子/分母（judged 数）

#### Scenario: ERROR 明细可见
- **WHEN** 报告存在 `ERROR` 用例
- **THEN** 报告中单列每条 `ERROR` 的用例 id 与失败原因

### Requirement: 门禁行为评测用例
评测用例集 SHALL 覆盖统一门禁的行为契约：重试类用例按 gate 的 `RETRYABLE` 语义重写，审批类用例覆盖"事实表全扫→审批"正例与"聚合表全扫→放行"反例。

#### Scenario: 重试用例对齐 gate 语义
- **WHEN** 运行 `hard_guard`/`dq` 类型用例（如 c15/c16）
- **THEN** 其期望（如 `sql_retry_count`、期望状态）按统一门禁的 `RETRYABLE`/`APPROVAL_NEEDED` 语义定义，不再依赖旧 validate/execute 分裂行为

#### Scenario: 事实表全扫触发审批
- **WHEN** 用例查询 FACT 表（`user_behavior_fact`/`play_detail`）且 EXPLAIN 为全表扫描
- **THEN** 评测断言最终状态为 `WAITING_APPROVAL`

#### Scenario: 聚合表全扫放行
- **WHEN** 用例仅查询 AGGREGATE 表（`metric_daily`）且 EXPLAIN 为全表扫描
- **THEN** 评测断言最终状态为 `SUCCESS` 且 SQL 正常执行

#### Scenario: mock 三态注入
- **WHEN** 以 `--platform mock` 运行门禁行为用例
- **THEN** mock 平台按 `verdict`（PASS/RETRYABLE/APPROVAL_NEEDED）注入门禁响应，驱动"事实表全扫→审批"等用例，无需真实 DB
