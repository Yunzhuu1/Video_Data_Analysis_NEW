# Main 全链路评测汇总（2026-08-22）

> 基线分支：`main`
>
> 基线提交：`437c64d`（包含 `snapshot-integrity-validation` 归档）
>
> 结论：确定性能力、指标召回和快照安全门槛通过；真实端到端暴露指标目录数据库迁移缺口，记忆近似泛化阈值与当前 embedding 模型不匹配。当前不应宣称 System Readiness 全绿。

## 1. 环境与基础测试

- Embedding：`doubao-embedding-vision-251215`，最小调用成功，2048 维，向量值有限。
- Python：256/256 通过并自然退出。
- Java：56/56 通过。沙箱内 Mockito/Byte Buddy 无法 attach JVM，沙箱外按相同命令重跑通过；这是执行环境限制，不是业务断言失败。
- Ruff：clean。
- Spring、Agent Engine、MySQL：均以当前 main 代码/本地 seed 42 数据完成真实联调。

## 2. 确定性门槛

| 项目 | 结果 |
|---|---:|
| Metric Recall judged | 49 |
| Recall@configured K | 49/49 |
| Strict Recall@effective K | 49/49 |
| 多指标完整召回 | 2/2 |
| Lineage Path Recall | 8/8 |
| Lineage expected rejection | 2/2 |
| Plan selection | 2/2 |
| N=61 mock 可执行性 | 61/61，0 error |

Mock L1 为 0 是 FakeLLM 协议本身不产出真实语义答案，不能作为模型质量数据。

## 3. 真实 LLM：Top-K 与 Full Catalog

运行口径：真实 LLM + mock platform + memory off；两次独立单轮，质量差异只作方向性观察。

| 指标 | Full | Top-K |
|---|---:|---:|
| Evaluated | 61/61 | 61/61 |
| E2E | 59/61（96.72%） | 60/61（98.36%） |
| L1 指标正确率 | 47/49（95.92%） | 49/49（100%） |
| L2 严格全字段 | 31/49（63.27%） | 30/49（61.22%） |
| L3 平均字段匹配 | 91.50% | 91.50% |
| Semantic user prompt chars avg | 1060 | 497 |
| Prompt 字符缩减 | - | 53.16% |

可靠结论：Top-K 把 Semantic user prompt 缩短 53.16%，本轮未观察到 L1 回退。不能把单轮 L1 +4.08pp 宣称为稳定提升；总 token 也未同比下降，因为 Planner/Answer 等后续调用仍占主要成本。

Top-K 的主要字段短板：time_range 33/49（67.35%）、ordering 42/49（85.71%）。唯一 E2E 失败为最终报告缺必需字段，指标解析仍正确。

## 4. 真实端到端（Spring + Agent + MySQL + LLM）

| 指标 | 结果 |
|---|---:|
| Evaluated / error | 61/61 / 0 |
| E2E | 60/61（98.36%） |
| L1 | 36/49（73.47%） |
| L2 | 25/49（51.02%） |
| R1 | 21/21（100%） |
| 风险拦截 / 自动修复 | 100% / 100% |

L1 从 mock platform 的 49/49 降到 36/49，不是 SQL 执行问题，而是平台指标目录漂移：

- Git `metric_catalog.json` 已有 15 个指标；
- MySQL `metric_definition` 和 Spring `/internal/metrics` 只有旧的 7 个指标；
- `DataInitializer.insertMetricDef()` 只在首次全量初始化调用，旧数据库启动时只增量补业务表，没有补新增指标；
- 新增 8 个指标因此无法进入真实平台的 Semantic/Recall 上下文。

R1 21/21 表明已经正确解析并进入可断言范围的 SQL 结果全部正确，但不能抵消目录缺失导致的 13 条 L1 错误。

## 5. 对抗评测

### Offline

- Harness PASS；case 11/11、variant 3/3、Audit 44/44。
- P05 三类快照漂移 3/3 SAFE_REJECT，compiler invocation 0/3，unsafe 0/6。
- Expected Disposition 10/11；P02 code 精度仍是已知 P2。

### Integrated（Hotfix 后新跑）

- Harness PASS；case 20/20、variant 3/3、ledger 完整。
- unsafe pass 0/12；Illegal Plan Rejection 6/7；Safety/Recovery 5/5；Recovery 3/3。
- Expected Disposition 14/20；Audit 70/71；R1 1/4；System Readiness FAIL。
- 剩余差异：C02-C04 Guard query-shape、P02 code 精度、S04/S05 未知指标处置。

### Directional-real N=7

- 7/7 有终态 observation，Semantic 3/5、Planner probes 0/2。
- 单轮小样本，仅作方向性观察，不作为发布门槛。

## 6. 记忆与 Embedding

### 同义/难层 A/B（有效）

- 使用真实 LanceDB + embedding，`degraded=false`，35 条。
- band：hit 0、inject 8、miss 27。
- 组 A L1 34/35（97.14%）；inject 子集 A 8/8 → B 8/8，增益 0。
- hard 层 14/15；当前基线已接近饱和，且多数问题不在记忆可达带，不能据此宣称记忆提升或无效。

### 真实会话 N=8（有效、方向性）

- 同问二次命中 8/8；ResolvedIntent 逐字段一致 8/8。
- close/reopen 文件持久化 8/8（弱验证）。
- 第二问相对第一问累计少 12,771 tokens。
- 说明“沉淀后同问直通”真实生效；N=8 不宣称显著性，服务器重启强持久化尚未在本轮执行。

### 虚拟澄清 N=35（上限实验）

- 无澄清基线 L1 34/35（97.14%），使用 golden 模拟完美用户选择后为 35/35，理论上限收益 +2.86pp。
- 潜在澄清 1/35，其中“歧义且错”0/35、“歧义但解析正确”1/35；没有观察到真正必须依赖 HITL 才能修复的样本。
- inject 8、miss 27；两个 seed 发生 embedding 失败，因此记忆 band 的次级观察不能作为完整覆盖结论，但不影响“虚拟澄清收益仅为上限、当前无真 HITL 必要证据”的主结论。
- 继续不实现真实 HITL 澄清符合当前 ROI；若未来真实业务歧义集出现“歧义且错”样本，再重新评估。

### 阈值与指纹标定（门槛失败）

- 当前 hit=0.92、inject=0.82 下，同义达到 inject 仅 19/35（54%），低于设计门槛 60%；近重复分数 0.807，低于 hit 阈值。
- 指纹阈值 0.5/0.6/0.7 均无法同时满足同义覆盖和毒化全拦；该增强默认关闭，因此未形成线上安全回退。
- 当前 embedding 模型与旧标定阈值不匹配，必须重新设计/标定后才能调整线上阈值。

### 冷热启动（无效，不计入产品指标）

热阶段发生间歇性 embedding DNS 失败和 LLM 降级，seed 不完整；runner 仅检查 key/model 是否配置，仍错误报告 `degraded=false`。其 `hot L1=0/35` 和 `-97.14pp` 是环境污染结果，禁止用于简历、回归或产品结论。原始日志保留用于修复 harness 的运行时健康度判定。

## 7. 新发现 Backlog

### P1

1. **平台指标目录迁移缺失**：Git catalog 15、真实数据库/API 7，直接导致真实端到端 L1 36/49。需要幂等 upsert/version migration，而不是手工改库。
2. **Agent 服务 Lance 启动路径错误**：`app.main` 在 lance backend 下仍把 `memory_db_path=memory.sqlite` 传入 Lance，已有 SQLite 文件时启动报 `File exists` 并禁用服务端记忆。实验使用临时 Lance 路径所以不受影响，真实服务受影响。
3. **运行详情类型转换失败**：真实服务日志出现 `LocalDateTime cannot be cast to java.sql.Timestamp`，`AgentRunQueryService.getRunDetail()` 会导致运行详情接口 500，影响审计记录查看。
4. **相对时间锚点格式不兼容**：真实 Agent 日志出现 `Invalid isoformat string: '2023-10-31T...'`；平台返回 timestamp，而相对时间展开按纯 date 解析，导致真实链路相对时间扩展失败或降级。

### P2

1. 为当前 embedding 模型重新标定混合检索；旧阈值不可直接沿用。
2. 评测 runner 必须把运行中 embedding 失败计入 observation/degraded 状态，不能只检查配置存在。
3. 对抗集剩余 C02-C04、P02、S04-S05 契约差异继续独立处理，不移动 expected。
4. time_range 是真实 LLM 严格字段的主要短板。

## 8. 最终判断

- 指标召回、血缘确定性门槛、快照完整性和同问记忆直通均有可信正向证据。
- 当前最大问题不是“LLM 能不能识别指标”，而是平台 catalog 数据迁移没有跟上代码 catalog；这是进入 release-readiness 前必须关闭的 P1。
- 应先修复 catalog 同步、服务端 Lance 初始化、运行详情类型转换与相对时间锚点格式，再重跑真实端到端与记忆集成；不建议现在直接冻结 RC1。
