## ADDED Requirements

### Requirement: 语义目录运行时就绪状态
Java 平台 SHALL 对受管指标目录执行启动 reconciliation，并发布可机读的运行时状态；状态 SHALL 至少包含 `status`、受管/ACTIVE 数量、受管/runtime catalog hash 与 missing/drifted/extra code 集合。受管资源非法、同步失败或回读漂移时平台 MUST fail-fast，不得以旧目录继续对 Agent 提供服务；数据库额外 code SHALL 仅告警且不得自动删除。

#### Scenario: 旧库启动后目录就绪
- **WHEN** MySQL 已有事实数据且 `metric_definition` 仅含旧 7 个指标，Spring 使用含 15 个受管指标的资源目录启动
- **THEN** 运行状态为 READY，15 个受管 code 均可经 `/internal/metrics` 查询，missing/drifted 为空，事实与聚合数据不变

#### Scenario: 目录不可修复时拒绝启动
- **WHEN** 资源包含重复/非法指标，或事务性 upsert 后回读 projection/hash 与资源受管 projection 不一致
- **THEN** reconciliation 回滚且 Spring 启动失败，不发布误导性的 READY，不允许 Agent 基于旧目录继续运行

#### Scenario: 额外指标非破坏性保留
- **WHEN** 数据库存在资源未管理的额外 ACTIVE 指标且全部受管指标一致
- **THEN** 状态为 READY 并在 `extraCodes` 告警，额外指标不被删除或停用，runtime hash 仍覆盖完整 ACTIVE 目录

### Requirement: Agent 记忆能力就绪状态
Python Agent SHALL 按 backend 选择唯一持久化路径（lance 使用 `memory_lance_path`，sqlite 使用 `memory_db_path`），并将记忆能力分类为 `READY | DISABLED | DEGRADED`。增强记忆初始化失败 SHALL 不阻断主分析链路，但 MUST 在 health/debug 中返回 backend、状态和稳定 reason code，不得仅打印异常后静默显示服务完全就绪。

#### Scenario: Lance 使用目录路径启动
- **WHEN** `memory_enabled=true`、`memory_store_backend=lance` 且 embedding provider 可用
- **THEN** Agent 使用 `memory_lance_path` 初始化 LanceDB，状态为 READY，不得把 `memory_db_path` 的 SQLite 文件交给 LanceDB

#### Scenario: 记忆初始化失败受控降级
- **WHEN** 配置路径形态非法、embedding 不可用或 store 初始化失败
- **THEN** 主服务仍可处理 `/analyze`，记忆状态为 DEGRADED 并带稳定 reason code，记忆读写控制 API 返回 503，原始异常仅写日志

#### Scenario: 记忆生命周期幂等关闭
- **WHEN** store 重初始化或 Agent 服务 shutdown
- **THEN** 已初始化 store 被至多一次安全 close；新 store 初始化成功后才替换旧引用，初始化失败不破坏仍可用的旧 store

### Requirement: Run Trace 读侧时间契约
Java Run Trace 查询 SHALL 使用显式 RowMapper 与统一时间适配器读取运行和节点时间，兼容 JDBC 返回的 `LocalDateTime`、`Timestamp` 与 `null`，不得依赖 `Map<String,Object>` 到 `Timestamp` 的强制转换。

#### Scenario: 查询已完成运行详情
- **WHEN** 数据库驱动把 `started_at/finished_at` 返回为 `LocalDateTime`，客户端查询该 run detail
- **THEN** API 返回 200，运行时间和按序节点轨迹完整，不发生 `LocalDateTime cannot be cast to Timestamp`

#### Scenario: 查询未完成运行详情
- **WHEN** run 的 `finished_at` 为 null 且已有部分 node trace
- **THEN** API 返回 200，`finishedAt=null` 并保留已有节点记录

