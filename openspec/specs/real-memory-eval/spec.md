# 真实路径记忆评测（real-memory-eval）

## Purpose

基于 real-session 协议测量记忆系统在真实路径（首问沉淀 → 跨请求/跨进程命中）的行为，产出与"场内自命中"口径分离的真实路径命中率基线，并保证评测不污染真实记忆库。

## Requirements

### Requirement: 真实路径记忆评测协议
评测 SHALL 支持 `real-session` 协议测量真实路径的记忆行为：以构造会话（首问沉淀 → 二问同文本命中 → 近似问变体）模拟真实用户路径，使用独立 `real-<ts>` namespace，产出与"场内自命中"分离的真实路径命中率基线。

#### Scenario: real-session 会话执行
- **WHEN** 以 `--protocol real-session --llm real` 运行评测
- **THEN** 用例按会话分组执行：首问（未命中，全链路成功后沉淀）→ 二问（同文本，期望 memory_hit=true）→ 近似问（变体，band 由运行时检索器分层）

#### Scenario: 真实路径命中率
- **WHEN** real-session 评测完成
- **THEN** 报告输出 `real_hit_rate`（二问起命中数 / 可命中机会数）、`real_consistency`（同问同答一致率）、`real_persist_hits`（跨进程持久化命中数），与场内 `memory_hit_rate` 并列并明确区分口径

#### Scenario: 跨进程持久化验证
- **WHEN** real-session 第一遍会话结束、记忆库重开（同一路径）后再次查询同文本
- **THEN** 命中仍在（记忆不依赖进程内状态），报告记录 `real_persist_hits`

### Requirement: 真实记忆库防污染
real-session 评测 SHALL 使用独立 `real-<ts>` namespace，默认不得写入 default（真实用户路径）记忆库；仅显式 `--namespace default` 联调开关可写真实记忆库，且该开关 SHALL 不进评测/CI 脚本。

#### Scenario: 默认隔离
- **WHEN** 运行 real-session 评测且未传 `--namespace default`
- **THEN** 所有读写发生在 `real-<ts>` namespace，default 条目不变

#### Scenario: 显式联调开关
- **WHEN** 真实联调需要沉淀真实记忆
- **THEN** 显式传 `--namespace default` 后写入 default；评测/CI 脚本不携带该参数
