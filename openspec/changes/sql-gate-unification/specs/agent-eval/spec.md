## ADDED Requirements

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
