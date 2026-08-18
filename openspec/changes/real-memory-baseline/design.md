## Context

记忆系统已具备：混合检索（LanceDB + 方舟 embedding，路径 B 自算融合）、namespace 隔离（eval-* 独立于 default）、评测协议（--memory on/off、重复对、毒化反例、注入/冷热实验）。但 `memory.sqlite` 实测只有 eval-* namespace 条目，**default（真实用户路径）为 0 条**——现有命中率 16-20% 全部是评测场内自命中（先沉淀后命中），不是真实场景数据。本 change 补"真实路径命中率基线"这一证据缺口。

约束：
- 评测不得污染 default 真实记忆库（memory-namespace-isolation 的设计不变式）。
- 写入门槛不变：全链路成功（sql_source=semantic + 执行成功 + DQ PASS/WARNING）才沉淀。
- 真实评测需真实 LLM（--llm real）；platform 可 mock（语义层）或 real（全链路）。

## Goals / Non-Goals

**Goals:**
- 产出真实路径命中率基线：跨请求命中、跨进程持久化命中、真实同问同答一致率。
- 口径分离：报告/指标明确区分「场内自命中（eval 协议）」与「真实路径命中（real-session 协议）」。
- 验证记忆真实生效的证据链：首问未命中 → 二问命中 → 近似问注入/未命中，逐会话可审计。

**Non-Goals:**
- 不写 default namespace（除非显式 `--namespace default` 联调开关，且不属于评测协议）。
- 不做真实用户流量采集/线上 A/B——本 change 用构造会话模拟真实路径，报告如实标注。
- 不做直通收益逐阶段计量（AnswerAgent 方差问题另立 change 解决；real-session 只记录总 token 并标注方向性）。
- 不动混合检索/阈值（memory-hybrid-retrieval 已标定 0.92/0.82/w=0.7）。

## Decisions

### D1：real-session 协议 = 会话分组 + 独立 namespace
在 runner 增加 `--protocol real-session`（与默认 `--protocol eval` 并列）：
- namespace = `real-<eval_date>-<start_ts>`（独立于 eval-* 与 default，一次评测一个，天然唯一）。
- 用例按**会话**分组：每个会话 = 首问（未命中，沉淀）→ 二问（同文本，期望命中）→ 近似问（变体，期望 inject/miss）。
- 会话集复用现有 golden cases 的子集（5-8 个代表性问题，覆盖 aggregate/trend/ranking/detail + 指标多样性），近似变体复用同义集 easy 层或人工构造。
- 近似问在本 change 中**仅作观测**（band 任意，按运行时检索器 top-1 分层报告，不预设）；若后续要演示真实路径的注入收益，需先离线验证近似变体 vs source 的融合分 ≥ inject_t（复用同义集 easy 层大概率落 inject，但必须显式校验——同 eval-data-expansion 的 band 前置打法）。
- 理由：构造会话是"真实路径"的最小可信模拟——它能验证跨请求命中与一致率，又不污染 default。**替代方案**（直接写 default）被否：破坏"评测不污染真实记忆"不变式。

### D2：口径分离——指标命名与报告
- 新指标前缀 `real_`：`real_hit_rate`（二问起命中数/可命中机会）、`real_consistency`（同问同答一致率）、`real_persist_hits`（持久化命中数）。
- **原始计数优先**：所有 `real_` 指标必须报告 x/y 原始计数而非只有百分比——8 个会话的二问+近似问可命中机会仅 ~16 次，单次 miss 即 6-12pp；报告统一标注「N=8 量级，方向性基线」，防「real_hit_rate=100%」被过度解读。
- `real_consistency` 复用 eval-metrics 重复对协议的逐字段定义：intent/metrics/dimensions/time_range/filters/ordering 逐字段一致（跨协议口径统一，报告可交叉引用）。
- 既有 `memory_hit_rate`（eval 协议）保持含义为"场内自命中"，报告明确标注。
- metrics-report 新增「真实路径基线」章节，与 §5 记忆价值（场内口径）并列、互相引用。
- 理由：口径混用是简历叙事最大风险——"16-20% 命中率"若被当作真实命中是误导；分离后两个数字各自站得住。

### D3：持久化验证（强弱双轨，报告分别标注）
- **弱验证（mock/runner 模式，自动化）**：第一遍会话结束后 `close()` store，同一路径重开后再查同文本，验证命中仍在——证明**文件持久化**（SQLite/LanceDB 落盘，不依赖进程内对象状态）。
- **强验证（real 模式，人工/联调）**：两遍 `/analyze`（首问 + 二问）**中间重启服务器进程**，同一 `MEMORY_LANCE_PATH` 下二问仍命中——证明**服务器进程重启后记忆仍在**（即「用户下次打开还在」）。
- 报告分别标注验证强度：`real_persist_hits`（弱，文件持久化）与 `real_persist_hits_strong`（强，进程重启）分开记录，避免「跨进程持久化」名不副实。
- 使用 runner 临时目录（与现有 eval 实验记忆同机制，`tempfile.mkdtemp`），不触碰真实 memory.sqlite/memory.lance。
- 理由：持久化是"真实生效"的关键证据；文件落盘与进程重启是两层 claim，必须分开验证与标注。

### D4：namespace 策略（防污染不变式）
- real-session 默认 `real-<ts>`，**绝不**写 default。
- `--namespace default` 显式开关仅供真实联调手动开启（写入真实记忆是联调动作，不进评测协议）；CI/评测脚本永不传此开关。
- 理由：memory-namespace-isolation 已确立"评测与真实隔离"；本 change 不倒退。

### D5：token 指标标注方向性
- real-session 记录每遍 API usage 总 token（首问 vs 二问），但因 AnswerAgent 方差（metrics-report §4.3），总 token 差只作为**方向性参考**，报告标注"解析阶段 token 需逐阶段计量（另立 change）"。
- 理由：避免重蹈 §4.3"N=1 反多"的误导。

## Risks / Trade-offs

- **[Risk] real-session 是构造会话，非真实用户流量** → 报告诚实标注"模拟真实路径（构造会话）"；真实命中率的最终证明仍需线上流量，本 change 提供方法论与基线的第一版。
- **[Risk] 近似问落 band 不确定**（同义改写可能 miss）→ 沿用 eval-metrics 的运行时 band 分层（runner 取检索器 top-1），近似问结果按 hit/inject/miss 分层报告，不预设。
- **[Risk] mock 平台下 LLM 关闭导致写入不触发** → real-session 协议强制 `--llm real`（真实 LLM 才可沉淀）；`--llm mock` 直接报错提示。
- **[Risk] 持久化验证依赖临时目录生命周期** → 验证路径与临时目录同生命周期，报告注明"验证用临时库，未触碰真实记忆文件"。

## Migration Plan

1. runner 增加 real-session 协议与指标（纯新增，不影响 eval 协议）。
2. 跑 `--memory off` 回归（N=45 不回退）→ 跑 real-session 真实评测（--llm real --platform real/mock）。
3. metrics-report 更新 + 开发日志追加；无部署/回滚（纯评测侧改动，运行时零行为变化）。

## Open Questions

- 会话数取 5 还是 8？（样本小则一致性口径弱，先取 8 看耗时）
- 近似变体优先复用同义集 easy 层，还是人工构造更贴近"用户真实改写"？（倾向复用，零新数据）
- （已解决）持久化验证采用强弱双轨：弱验证重开 store（自动化），强验证重启服务器（real 模式联调）。
