## MODIFIED Requirements

### Requirement: 真实路径记忆评测协议
评测 SHALL 支持 `real-session` 协议测量真实路径的记忆行为：以构造会话（首问沉淀 → 二问同文本命中 → 近似问变体）模拟真实用户路径，使用独立 `real-<ts>` namespace，产出与“场内自命中”分离的真实路径命中率基线。报告 SHALL 区分 store close/reopen 的弱文件持久化与真实 Agent 服务器使用配置后端中间重启的强持久化；只有后者可称为跨进程/下次打开仍命中。

#### Scenario: real-session 会话执行
- **WHEN** 以 `--protocol real-session --llm real` 运行评测
- **THEN** 用例按会话分组执行：首问（未命中，全链路成功后沉淀）→ 二问（同文本，期望 memory_hit=true）→ 近似问（变体，band 由运行时检索器分层）

#### Scenario: 真实路径命中率
- **WHEN** real-session 评测完成
- **THEN** 报告输出 `real_hit_rate`（二问起命中数 / 可命中机会数）、`real_consistency`（同问同答一致率）、`store_reopen_hits`（弱验证）与 `server_restart_hits`（强验证），均带原始分子/分母且不得把两个持久化口径混称为跨进程

#### Scenario: 服务器重启强持久化验证
- **WHEN** real-session 第一遍会话结束，确认 Agent health 的 memory backend/status 为预期 READY，停止并以相同配置路径重新启动服务器后再次查询同文本
- **THEN** 同 namespace 条目仍命中，报告记录 `server_restart_hits`、重启前后 backend/status 与原始计数；若 memory 为 DEGRADED 则协议 NOT_ASSESSED，不以 sqlite/进程内替代品冒充 Lance 结果

#### Scenario: Store 重开弱持久化验证
- **WHEN** runner 只 close store 并在同一 runner 进程重开同路径
- **THEN** 命中仅记录为 `store_reopen_hits` 弱文件持久化证据，不命名为服务器重启或跨进程验证

