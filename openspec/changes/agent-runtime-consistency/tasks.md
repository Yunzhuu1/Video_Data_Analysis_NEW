## 1. 指标目录控制面与旧库迁移

- [ ] 1.1 从 `LineageCatalogService` 抽取 Java 共享 `MetricCatalogProjection`，固定受限 canonical 字段/排序/hash；增加与 Python/既有 fixture 一致的固定 hash 测试，禁止 Synchronizer 与 lineage snapshot 各算一套
- [ ] 1.2 抽取 classpath metric catalog loader/validator：校验数组、必需字段、metricCode 唯一、dimensions 类型、source/time 字段与 schema 注册表、可用表达式及 lineage metric 引用，非法资源以稳定诊断 fail-fast
- [ ] 1.3 实现事务性 `MetricCatalogSynchronizer`：按 metric_code insert/update 受管字段，只有 projection 实际变化才 UPDATE/version+1；失败整体回滚，extra code 只告警不删除
- [ ] 1.4 将 catalog reconciliation 从 `DataInitializer.hasData()` 解耦并固定在 seed 数据初始化前执行；移除首次灌库专属 `insertMetricDef()` 路径，确保 initializer 开关/事实表是否有数据均不造成受管目录漂移
- [ ] 1.5 发布只读 catalog runtime status（READY、managed/active count、managed/runtime hash、missing/drifted/extra codes）并接入 Actuator 或受保护 internal readiness；复用同一 projection 让 lineage snapshot 在 15 指标旧库升级后可构建
- [ ] 1.6 增加 Java/MySQL 迁移回归：旧 7→15、已存在公式更新、重复启动幂等/version 不增、非法/写入失败回滚、extra 保留、事实/聚合 checksum 与既有 R1 真值不变、`/internal/metrics` 15 code 与 lineage snapshot 成功

## 2. Agent 记忆启动与能力状态

- [ ] 2.1 实现唯一 memory path resolver/bootstrap：lance→`memory_lance_path`、sqlite→`memory_db_path`，FastAPI lifespan 使用配置路径；评测显式 path/backend 保持隔离且优先
- [ ] 2.2 实现 memory `READY|DISABLED|DEGRADED` 状态和稳定 reason code，初始化失败保持主链路可用但禁用读写；禁止只打印异常后 `/health` 仍无差别显示 UP
- [ ] 2.3 补齐 store 生命周期：新 store 初始化成功后原子替换，重初始化/服务 shutdown 幂等 close，失败不破坏仍可用旧 store；控制 API 非 READY 返回 503
- [ ] 2.4 扩展 Python health/debug schema（不暴露路径、原始异常、凭据），增加 sqlite/lance 路径选择、文件/目录冲突、embedding 不可用、初始化异常、替换失败与 close-once 测试；增加完整 graph 断言：DEGRADED + nodes.memory=None 时检索/注入/写入零调用 store、主链路正常、memoryHit 不误报、sqlSource 语义不变、health 保留 reasonCode

## 3. Run Trace 读侧契约

- [ ] 3.1 将 `AgentRunQueryService.getRunDetail()` 改为显式 RowMapper，抽取统一时间适配器兼容 `LocalDateTime`、`Timestamp`、`java.sql.Date` 与 null，未知 JDBC 类型给出可诊断错误
- [ ] 3.2 增加 service/MySQL 集成测试：已完成和运行中 run、多个有序 node、finished_at=null/非空均返回完整 DTO；增加真实 Run Detail HTTP 200 smoke，防止 controller mock 掩盖驱动类型问题

## 4. 相对时间跨语言锚点

- [ ] 4.1 实现共享 physical anchor binding：active lineage 只使用 validated plan 的 sourceTable/timeFieldRef，legacy 使用 `_resolve_path` 后物理 source/time 表达式；锚点 SQL 固定 `MAX(DATE(...)) AS anchor_date` 并与最终过滤同源
- [ ] 4.2 新增 `normalize_anchor_date` 边界函数，兼容 date/datetime/ISO date/ISO datetime（含 timezone）并只向 `time_expand` 传 YYYY-MM-DD；null/空行/非法值保留 warning + 受控降级
- [ ] 4.3 增加 Python 单元/图集成与真实平台契约测试：metric_daily、fact 路由、validated plan、时间戳 JSON、带 timezone、非法锚点和最近 7 天含端点，断言不再出现 `Invalid isoformat`

## 5. 集成门槛、真实评测与材料

- [ ] 5.1 运行 Java/Python 全量、ruff、OpenSpec strict 与 diff 检查；先满足 catalog/memory/trace/time 全部确定性 contract，失败时不得移动 golden/expected 或手工补库
- [ ] 5.2 在真实 Spring + Agent + MySQL + embedding 环境执行 runtime smoke：15 code、catalog/hash readiness、lineage snapshot、新增/比率/去重/相对时间代表查询、Run Detail、Lance READY 与中间服务器重启后同 namespace 命中
- [ ] 5.3 仅在 5.1/5.2 通过后定向重跑 N=61 real-real memory-off、integrated adversarial、real-session N=8；按 D7 固定清单输出 12 个结构性不可达 case 的 before/after（missing→reachable）逐例表、invalid_catalog fallback 59→0、R1 相对 21/21 不回退和原始 L1-L4；n19 单列为非确定性差异，不把随机 L1 或小样本记忆结果宣称为显著提升
- [ ] 5.4 将 after 证据与 `release-main-2026-08-22` 修复前基线并列归档，更新 `docs/开发日志.md` 与 `docs/面试素材库.md`，记录确定性结论、方向性结果、剩余 backlog 与面试可讲的跨层排障/一致性设计
