## Why

`main@c5735c0` 的真实 Spring + Python Agent + MySQL + LLM 评测暴露出“模块测试正确、真实运行态不一致”：mock platform 的指标 L1 为 49/49，而真实链路仅 36/49，根因是 Git 指标目录已有 15 个指标、旧 MySQL/Spring API 仍只有 7 个；同时服务端 LanceDB 因路径选择错误被静默禁用，Run Detail 存在 Java Time 强转 500，相对时间锚点存在 timestamp/date 跨语言解析失败。进入 RC 前必须建立 Java 语义控制面与 Python Agent Runtime 之间可验证、可审计的运行时一致性契约，而不是继续用 mock 成绩掩盖真实部署漂移。

## What Changes

- 将指标目录同步从 `DataInitializer` 的“首次事实数据灌库”分支中解耦，新增独立启动 reconciliation：校验 classpath `metric_catalog.json`、按 `metric_code` 事务性幂等 upsert、回读权威字段并输出 count/hash/drift 状态；资源指标缺失或漂移无法修复时 fail-fast，数据库额外指标只告警且不删除。
- 固定 Agent 记忆后端路径契约：`lance -> memory_lance_path`、`sqlite -> memory_db_path`，保留评测显式临时路径；将记忆运行态建模为 `READY | DISABLED | DEGRADED`，初始化失败不阻断主链路但必须通过 health/debug 暴露稳定 reason code，禁止静默失效。
- 统一 Agent Run 读侧时间映射，移除 `queryForMap + Timestamp` 强转，兼容 `LocalDateTime`、`Timestamp` 与 `null`，保证运行详情可返回完整节点审计记录。
- 固定相对时间锚点跨语言契约：锚点 SQL 返回数据末日 `DATE`，Python 展开边界兼容 date/datetime 值并归一为日期；失败仍按既有 warning + 受控降级语义处理。
- 增加真实运行时契约与集成回归：旧 7 指标数据库升级到 15、重复启动幂等、catalog hash/投影一致、真实 Lance 启动与重开、Run Detail 200、相对时间真实平台展开；随后定向重跑真实 N=61、integrated adversarial 和 real-session，不承诺 LLM 随机单轮全绿，只要求 catalog-caused failures 归零且既有 R1 不回退。
- 不在本 change 引入 Flyway/Liquibase、图数据库、HITL、Skill 自进化、LLM 自动修改权威指标口径、前端或评测 runner 的 embedding 运行时健康重构。

## Capabilities

### New Capabilities
- `agent-runtime-readiness`: 定义指标目录 reconciliation、Agent 组件健康状态、Run Trace 时间映射和跨语言相对时间锚点的真实运行时一致性契约。

### Modified Capabilities
- `semantic-resolution`: “指标字典落地”从仅支持空库种子扩展为旧库启动时也必须幂等同步、回读验证并向 Agent 提供完整权威目录；相对时间锚点明确 date/datetime 归一化边界。
- `agent-eval`: 增加 runtime consistency 定向回归与修复前后归因口径，区分确定性 catalog-caused failure、R1 回归和真实 LLM 单轮方差。
- `real-memory-eval`: 将持久化强验证明确扩展为真实 Agent 服务使用配置后端启动、健康状态 READY、服务器重启后同路径命中；store close/reopen 仍仅作为弱文件持久化证据。

## Impact

- Java：`DataInitializer`、新增 catalog synchronizer/readiness、`MetricCatalogService`、lineage snapshot 运行态、`AgentRunQueryService`、Actuator/内部健康 DTO 与测试。
- Python：`app.main`/settings/`graph_builder.init_memory`、health/debug schema、相对时间 anchor/`time_expand`、运行时集成测试。
- 数据：`metric_definition` 权威字段会在旧库启动时按资源目录新增或更新；不删除额外指标，不重灌或修改 seed 42 事实数据与既有 R1 真值。
- API：现有分析与治理接口保持兼容；健康/观测响应新增可选 catalog 与 memory 状态字段。
- 评测：复用 `docs/eval-reports/release-main-2026-08-22/` 作为修复前基线，新增定向 after 报告；BUG-021 embedding runner 健康误判另立 change。
