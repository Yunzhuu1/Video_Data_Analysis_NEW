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

#### Scenario: 报告含结果正确率
- **WHEN** 运行 real 平台评测
- **THEN** 报告包含 R1（结果正确率，可断言用例口径）与 L1-L4 并列，并含 `L1 对 + R1 错` 交叉诊断清单

#### Scenario: relative 时间用例纳入 R1
- **WHEN** relative 时间语义修复后运行 R1 评测
- **THEN** relative 可断言子集（aggregate/trend 用例，如 c03 最近7天）纳入断言范围，合成 SQL 含时间过滤且结果与 seed 42 真值一致（R1 扩展到 relative 子集全绿）；detail/歧义 relative 用例仅验证 SQL 形态（R1=N/A 不变）

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

### Requirement: 审批暂停用例的评测语义
评测 SHALL 区分两类审批暂停用例的判定：risk 类型用例（期望 `WAITING_APPROVAL`）拦截即 PASS；其余类型用例若被门禁拦截，runner SHALL 自动调用审批接口放行，验证审批后完整链路并产出报告后再判字段/关键词。

#### Scenario: risk 用例拦截即通过
- **WHEN** 用例类型为 risk 且最终状态为 `WAITING_APPROVAL`
- **THEN** 该用例判定 PASS（拦截=正确行为），不要求报告字段

#### Scenario: 其余类型自动放行补跑
- **WHEN** 非 risk 用例在 real 模式收到 `WAITING_APPROVAL`
- **THEN** runner 自动调用 `POST /api/agent/runs/{runId}/approval` 放行，等待执行结果并产出报告，再继续字段/关键词检查

#### Scenario: 回答质量必填项
- **WHEN** 用例的 `expected_report_fields` 含 `metrics`
- **THEN** 最终报告 metrics 非空（LLM 缺省时由查询结果兜底）；`expected_report_keywords` 命中报告文本（DQ 警告必须带入回答）

#### Scenario: 评测保真度自证
- **WHEN** 评测报告输出
- **THEN** 报告包含 `auto_released` 计数/比例（非 risk 用例被门禁拦截后自动放行的数量/占比），并与端到端成功率并列展示，使"门禁不过度拦截"可审计

### Requirement: 记忆行为评测
评测 SHALL 隔离记忆对回归的影响：回归评测默认 `--memory off`；记忆行为（重复问题对、相似反例、命中率）由 `--memory on` 专用用例覆盖，且 `--memory on` 使用独立记忆库（跑完即弃）。命中率报告 SHALL 区分**场内自命中**（eval 协议）与**真实路径命中**（real-session 协议），不得混用口径。

#### Scenario: 命中率口径分离
- **WHEN** 生成评测报告
- **THEN** `memory_hit_rate` 标注为场内自命中口径（eval 协议）；真实路径命中率使用 `real_` 前缀指标（real-session 协议），两者并列展示且各自注明来源

#### Scenario: 回归隔离
- **WHEN** 运行 golden cases 全量回归
- **THEN** 记忆默认关闭，解析结果不来自记忆（防止记忆掩盖解析回归）

#### Scenario: 重复问题同问同答
- **WHEN** 同一 question 在开启记忆下连续运行两次（两遍都成功解析）
- **THEN** 第二次 `memory_hit=true` 且 resolvedIntent 与第一次逐字段一致（一致率 100%）

#### Scenario: 相似反例不误命中
- **WHEN** 记忆库只有"最近7天播放量"，查询"最近7天点赞量"
- **THEN** 该查询不得命中（band != hit），避免静默错误指标

#### Scenario: 命中率可观测
- **WHEN** 评测报告生成
- **THEN** 包含 `memory_hit_rate` 与 `memory_inject_rate`，与 L1-L4 并列展示

### Requirement: 记忆评测自隔离
评测 SHALL 通过 eval namespace 实现记忆自隔离：`--memory on` 使用独立 eval namespace（per-eval，如 `eval-<eval_date>-<start_ts>`），启动时清空该 namespace，反例预置写入该 namespace；真实记忆（default namespace）SHALL 不受评测影响。

#### Scenario: eval namespace 自隔离
- **WHEN** 运行 `--memory on` 评测
- **THEN** 评测使用独立 eval namespace（per-eval，一次评测一个），无需服务端 `MEMORY_DB_PATH` 切换或手动删库；评测前后 default namespace 条目不变

#### Scenario: 反例真预置（毒化变体）
- **WHEN** 运行相似反例用例（real 模式）
- **THEN** 预置"毒化变体"（问题文本与 intent 指标不一致）通过 `POST /internal/memory/seed` 写入 eval namespace（服务器 store）；查询同文本（相似度 ≥ 直通阈值）时 metrics 一致性校验拦截，band != hit

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: golden 覆盖度
- **WHEN** 评测数据集（golden cases）包含多指标组合、多条件过滤、排名+时间嵌套、跨表 JOIN、长尾/歧义等场景
- **THEN** 每个可判定用例标注 `golden_spec`，可参与口径正确率统计；歧义题可不标 golden_spec（仅端到端统计）

#### Scenario: 难层客观筛选
- **WHEN** 对同义集 hard 层候选运行无记忆基线（组 A）并计算运行时 band（与线上同一检索器）
- **THEN** 仅保留 **组 A L1<100% 且 band=inject** 的条目为"真难层"；band=miss 的难层条目归入"miss 泛化层"单独报告；hard 层若无真难层，报告如实标注"注入不可达或无增益"，不硬凑

#### Scenario: 指标表达覆盖
- **WHEN** 指标表达映射（别名/指纹）新增条目
- **THEN** 评测数据集含对应覆盖用例（至少 1 个 golden/同义用例），且真实评测报告别名匹配命中情况（alias_hit）

#### Scenario: 多指标用例语义路径验证
- **WHEN** 运行 --memory off 全量回归
- **THEN** 同源表多指标用例（如 n01 播放量+点赞量）sql_source=semantic 且 L1 正确；跨源表多指标用例（如 n02 完播率+互动率）保持 fallback 并在报告标注已知边界

### Requirement: 量化指标测量
评测 SHALL 支持量化指标的测量与报告：token 计量（LLM 调用 usage）、同义表达问题集的注入收益/冷热启动实验、以及可写进简历的指标报告（含历史轨迹与对比基线）。同义集实验的 band 分层 SHALL 取自**与线上同一实现**的检索器（混合检索），报告 SHALL 注明**检索器实现/阈值/embedding 模型**三变量配置，并按**难度分层**（easy/hard）输出注入收益。

#### Scenario: token 计量
- **WHEN** 运行 real 模式评测
- **THEN** 每用例记录 LLM token 消耗（prompt/completion/total）；命中直通仅消除解析阶段 token（用例总 token 仍含回答阶段），报告以"命中 vs 未命中用例总 token 差"衡量

#### Scenario: 同义集注入收益（按波段分层，band 运行时取自检索器）
- **WHEN** 以同义表达问题集（YAML 存 question/golden/source_case/difficulty，不静态标 band）运行无记忆（--memory off）与有记忆（--memory on，先沉淀后同义集）两组，band 由 runner 对每条同义问题执行**与线上同一实现**的检索（取 top-1）
- **THEN** 报告对比 **inject 波段子集**的 L1 口径成功率与 inject 命中率；miss 波段子集单独报告（LLM 自身泛化）；hit 波段归直通实验；报告注明**检索器实现/阈值/embedding 模型**三变量（如 `hybrid(doubao-embedding-vision-251215)/0.92-0.80/w=0.7`）

#### Scenario: 难层注入收益（按难度分层）
- **WHEN** 同义集包含 `difficulty: hard` 条目，且已通过组 A 实测筛选（保留 **L1<100% 且 band=inject** 的真难层）
- **THEN** 报告分别输出 easy / hard（真难层）/ miss 泛化层的 N、组 A L1、组 B L1 与注入增益，附逐例翻转四列表；hard 层增益 >0 说明注入示例将错误改写掰回正确，=0 则如实报告"该难度层注入无增益"（最小声明口径：至少 1 例翻转，不宣称显著提升）

#### Scenario: 冷热启动（检索侧）
- **WHEN** 以空记忆（冷）与预置记忆 seed（热）分别运行同义集
- **THEN** 报告对比成功率与延迟（实验仅测检索侧，消除写路径方差，区别于全链路注入实验）

#### Scenario: 阈值标定可复现
- **WHEN** 生成混合检索的阈值标定报告
- **THEN** 输出同义集/毒化对/近重复对三组相似度分布，标注 hit 阈值（毒化对全部落于其下的最小值）与 inject 阈值（期望注入条目全部落于区间内的最大值），阈值可复现

#### Scenario: 指标报告
- **WHEN** 生成 `docs/metrics-report.md`
- **THEN** 包含历史轨迹表（逐轮端到端/L1/拦截率/命中率，附 commit）、正确性/安全/效率/记忆价值指标、实验协议与可复现说明，以及样本量 N 与难度分层
