## ADDED Requirements

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
