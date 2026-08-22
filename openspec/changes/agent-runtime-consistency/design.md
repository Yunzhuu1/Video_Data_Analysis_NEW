## Context

`main@c5735c0` 的修复前基线同时证明了两个事实：确定性模块本身可用（Metric Recall 49/49、Lineage Path Recall 8/8、R1 21/21），但真实 Spring + Agent + MySQL 链路的 L1 仅 36/49。Git `metric_catalog.json` 有 15 个指标，旧 MySQL `metric_definition` 与 `/internal/metrics` 只有 7 个；`DataInitializer` 仅在 `user_behavior_fact` 为空时调用 `insertMetricDef()`，所以扩目录对旧库永不生效，lineage snapshot 也因缺少 `video_revenue` 等 code 失败。

同一次联调还发现三个运行时契约缺口：FastAPI lifespan 在 lance backend 下仍把 `memory_db_path=memory.sqlite` 传给 LanceDB，异常被捕获后服务显示 UP 但记忆实际禁用；`AgentRunQueryService.getRunDetail()` 将 `queryForMap()` 返回的 `LocalDateTime` 强转 `Timestamp`；相对时间锚点经 SQL/JSON 返回 datetime 字符串，而 `time_expand()` 只接受 ISO date。它们共同说明需要治理“权威上下文与能力状态如何从 Java 控制面进入 Python Agent”，而不是继续添加 Agent 功能。

约束：项目是个人学习/秋招项目，使用 MySQL seed 42 与 classpath catalog；不引入新的迁移框架或基础设施。指标口径是权威配置，不允许 LLM 自动改写。现有 API 向后兼容，记忆仍是可降级增强能力，SQL/结果安全边界不改变。

## Goals / Non-Goals

**Goals:**

- 让已有 7 指标的旧数据库在 Spring 启动时自动、事务性、幂等地补齐并更新到资源目录的 15 个受管指标，且不修改事实数据。
- 用同一份规范化 projection 与既有 `CanonicalJson` 计算/比较资源和数据库指标 hash，不能以 count 相等替代内容一致。
- 让 catalog 同步状态和 Python memory 状态可机读、可审计；权威 catalog 不可信时 fail-fast，增强记忆失败时受控降级。
- 让 Run Detail 与相对时间锚点在 JDBC、Jackson、HTTP、Python 边界上有明确类型契约。
- 以修复前固定基线重跑真实集成协议，分离确定性故障消除、R1 回归和 LLM 单轮方差。

**Non-Goals:**

- 不引入 Flyway/Liquibase，不设计多环境 Catalog 发布平台、审批流或自动回滚。
- 不自动删除数据库额外指标，不由 LLM/记忆自动修改指标公式、血缘或状态。
- 不调整 embedding 阈值、metric fingerprint、LLM prompt、Planner 策略或对抗集 expected。
- 不修 BUG-021（runner 仅按配置判断 embedding degraded）；该问题独立处理。
- 不新增前端、图数据库、HITL、多 Agent 或 Skill 自进化。

## Decisions

### D1：Catalog reconciliation 独立于事实数据初始化

新增 Spring `MetricCatalogSynchronizer`（独立开关，默认随当前 demo profile 启用），不再由 `DataInitializer.hasData()` 决定是否同步。Spring schema 初始化完成后，Synchronizer 在 `DataInitializer` 之前运行；`DataInitializer` 只负责 seed 42 维度/事实/聚合/规模化表。无论事实表是否已有行，catalog reconciliation 都执行。

启动流程固定为：

```text
load classpath metric_catalog.json
  → validate resource
  → transaction(upsert each managed metric)
  → read back active managed codes
  → normalize both projections
  → compare managed projection + hash
  → publish READY or fail startup
```

选择启动 reconciliation 而不是手工 SQL，是为了让“新库”和“升级旧库”行为一致；本项目暂不引入 Flyway，是因为 schema 已由 `schema.sql` 管理，当前问题是可变业务目录数据而非 DDL 版本链。

### D2：受管字段事务性 upsert，额外指标不删除

以 `metric_code` 为自然键，单事务执行 MySQL `INSERT ... ON DUPLICATE KEY UPDATE`。资源拥有并更新：`metric_name/business_definition/formula/dimensions/time_granularity/source_table/time_field/fact_formula/fact_event_filter/status=ACTIVE`；保留数据库拥有的 `id/owner/created_at`。只有内容实际变化时 `updated_at` 变化；`version` 在受管 projection 实际变化时递增，纯重启不得递增。

资源校验至少包含：顶层为数组、非空且 `metricCode` 唯一；必需字符串非空；dimensions 为字符串数组；`sourceTable/timeField` 在 `TableSchemaRegistry` 存在；formula 至少一个可用表达式；lineage 引用的 metric code 必须属于同步后的 active 集合。任一受管指标无法写入或回读不一致，事务回滚并使 Spring 启动失败。

数据库中不属于资源的 code 记为 `extraCodes` 并告警，但不删除、不停用，也不纳入“managed projection 一致”失败条件；运行时完整 metric hash 仍按 `/internal/metrics` 全部 ACTIVE 指标计算，避免把 extra 隐藏。当前 seed 42 验收要求无 extra，activeCount=managedCount=15。

### D3：Catalog projection/hash 只实现一次语义

从 `LineageCatalogService.normalizeMetrics()` 抽取共享的 `MetricCatalogProjection`：固定字段为 `metricCode/formula/dimensions/sourceTable/timeField/factFormula/factEventFilter`，按 metricCode 排序，dimensions 排序；使用既有 `CanonicalJson` 受限规范计算 SHA-256。Synchronizer、lineage snapshot 和测试 fixture 必须复用该 projection，不各写一套 hash。

发布只读 `MetricCatalogRuntimeStatus`：

```json
{
  "status": "READY",
  "managedCount": 15,
  "activeCount": 15,
  "managedCatalogHash": "...",
  "runtimeCatalogHash": "...",
  "missingCodes": [],
  "driftedCodes": [],
  "extraCodes": []
}
```

状态通过 Spring Actuator health detail 或等价 internal readiness 端点暴露；未授权公共响应不暴露公式、SQL、连接信息。`LineageCatalogService.snapshot()` 继续发布完整运行时 `metricCatalogHash`，并且在 reconciliation READY 后必须成功构建。

### D4：Memory 后端、路径和生命周期成为显式运行时状态

增加纯函数 `resolve_memory_path(settings, backend)`：lance 唯一使用 `memory_lance_path`，sqlite 唯一使用 `memory_db_path`。FastAPI lifespan 不再自行传错字段，而是调用统一 bootstrap；评测仍可向 `init_memory(explicit_path, backend)` 传显式隔离路径，显式参数优先但必须与 backend 的文件/目录形态兼容。

状态机固定为：

```text
memory_enabled=false                         → DISABLED
enabled + configured backend init succeeds → READY
enabled + provider/path/store init fails    → DEGRADED(reasonCode)
```

`DEGRADED` 不阻断 `/analyze`，`nodes.memory=None`，但 `/health` 必须返回 `memory.enabled/backend/status/reasonCode`；reason 只使用稳定枚举（如 `EMBEDDING_UNAVAILABLE`、`INVALID_STORE_PATH`、`STORE_INIT_FAILED`），原始异常只写服务日志。启动成功、重初始化或 shutdown 时对 store 执行一次 close；新 store 完成初始化后再原子替换旧引用，失败不得破坏仍可用的旧 store。测试/调试 seed API 在非 READY 时继续返回 503。

### D5：Run Detail 使用 RowMapper 和统一 Java Time 适配

`getRunDetail()` 不再使用 `queryForMap()` 后强转，而与列表/节点查询一样使用显式 RowMapper。共享适配器接受 `null`、`LocalDateTime`、`Timestamp`（必要时兼容 `java.sql.Date`），转换成 DTO 的 `LocalDateTime`；未知类型抛包含 JDBC 类型名的明确异常。读取行为不改表结构、不改写已有 trace。

集成验收必须先真实创建一条包含多个 node、`finished_at` 可空/非空的 run，再通过 API 查询；只 mock controller 不能证明驱动返回类型兼容。

### D6：相对时间锚点绑定实际物理路径并在边界归一化

锚点不是从 metric definition 原始 `timeField` 猜测。active lineage 计划存在时，使用 validated plan 的 `sourceTable + timeFieldRef`；legacy 路径使用 `_resolve_path` 后 source 对应的物理时间表达式。锚点 SQL 固定为 `SELECT MAX(DATE(<physical_time_expr>)) AS anchor_date ...`，与最终合成 SQL 的时间过滤来源一致。

`normalize_anchor_date(value)` 是唯一 Python 边界：接受 `date`、`datetime`、`YYYY-MM-DD`、ISO datetime（含 timezone），归一为 `YYYY-MM-DD`；`None`、无法解析或无结果抛稳定错误，由现有节点捕获并记录 warning 后受控降级。`time_expand()` 只消费该规范 date，避免在纯函数内部继续扩散平台类型兼容逻辑。

### D7：评测以“可归因错误归零”为硬门槛，不绑定随机 L1 全绿

修复前证据固定为 `docs/eval-reports/release-main-2026-08-22/`。实现后分三层：

1. deterministic/contract：旧 7 指标 fixture → 15 managed 指标、两次同步幂等、projection/hash 一致、事实表 checksum 不变；memory path/status/lifecycle；Run Detail；anchor date/datetime。
2. integrated smoke：Spring + Agent + MySQL 下 `/internal/metrics` 15、lineage snapshot 成功、代表性新增/比率/去重/相对时间查询成功、Run Detail 可审计、真实服务 Lance READY 且中间重启后命中。
3. directional real：`--llm real --platform real --memory off` N=61、integrated adversarial、real-session N=8。报告原始计数、模型/时间/commit；LLM 指标只作单轮方向性。

硬门槛：catalog-caused failures 13→0；资源 15 个 code 全部出现在 API 与 Agent catalog；R1 可断言子集相对 21/21 不回退；事实数据真值不变；Run Detail 200；相对时间不再出现 datetime parse warning；memory 强验证明确区分服务器重启与 store reopen。整体 L1 不写死 49/49，避免用随机模型结果决定确定性修复是否正确。

## Risks / Trade-offs

- [启动 fail-fast 降低可用性] → 只对权威受管 catalog 的非法/缺失/漂移 fail-fast；额外数据库指标告警放行，记忆失败仍降级。
- [upsert 意外覆盖人工修改] → 明确 classpath 资源是 demo 受管 code 的权威源，仅覆盖列出的受管字段；owner 与额外 code 保留，日志列出 changed codes。
- [version 每次启动误增] → 更新前比较规范化受管字段，仅实际变化才 UPDATE/version+1；补二次启动断言。
- [事务成功但 readiness/hash 实现不同] → reconciliation 与 lineage snapshot 复用同一 projection/CanonicalJson，并用固定 fixture hash 测试。
- [健康接口泄漏内部信息] → 只暴露状态、计数、hash、code 差异和稳定 reason；不暴露公式、路径、异常堆栈或凭据。
- [Lance close/替换引入并发竞态] → 在 lifespan/bootstrap 串行初始化；先建新 store 再替换，shutdown 幂等 close，运行中不提供热切 backend API。
- [DATE 截断改变时区语义] → 数据末日按数据库业务日期定义，SQL 侧 DATE 化；本 change 不支持用户时区日界线，作为后续边界明确记录。
- [真实 LLM 方差掩盖确定性收益] → 以 catalog code 覆盖、失败根因分类和 R1 为硬门槛，L1 仅报告原始单轮结果。

## Migration Plan

1. 先补 catalog projection、资源校验与旧 7 指标 fixture；实现 synchronizer 但暂不删除旧 `insertMetricDef()`。
2. 在同一事务/测试证明旧库补齐、字段更新、重启幂等和事实 checksum 不变后，将 catalog 调用从 `DataInitializer` 移除，固定执行顺序。
3. 接入 Spring catalog readiness 与 lineage snapshot 回归；失败时回滚事务并阻止启动。回滚代码版本不会删除已新增指标，旧版本会忽略它们。
4. 修正 Python memory bootstrap/lifecycle 与 health，再修 Run Detail 和 anchor contract；均保持现有 API 字段兼容。
5. 跑 Python/Java 全量、contract/integrated smoke；满足确定性门槛后再运行成本较高的真实 N=61、adversarial integrated、real-session。
6. 将 after 证据与修复前 baseline 并列归档并更新开发日志/面试素材。若确定性门槛失败，不调整 golden/expected，不进入 RC。

## Open Questions

- 无阻塞项。默认决策已定：受管 catalog 不可修复则 fail-fast；额外 code 只告警；记忆失败 DEGRADED；真实质量不承诺随机 L1 全绿。
