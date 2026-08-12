# LangGraph 编排

## Purpose

基于真 LangGraph 的编排：状态图驱动、HITL 审批持久化恢复、审批后不重新生成 SQL、对外 facade 稳定。

## Requirements

### Requirement: 编排基于真 LangGraph 状态图
编排层 SHALL 使用 `langgraph.graph.StateGraph` 定义节点与条件边，不得再使用手写 while 循环表达主流程。

#### Scenario: 主链路由编译图驱动
- **WHEN** 调用 `run_chatbi_graph(state)`
- **THEN** 执行经由编译后的 `StateGraph`，节点跳转由条件边决定

#### Scenario: 重试回环由条件边表达
- **WHEN** `SQL_HARD_GUARD`/`SQL_VALIDATE`/`SQL_SOFT_DQ` 判定失败且 `sql_retry_count < 3`
- **THEN** 条件边回到 `SQL_GENERATE`，且 `sql_retry_count` 递增

### Requirement: HITL 审批可持久化恢复
高风险 SQL 审批 SHALL 通过 `interrupt()` + 持久化 checkpointer 实现；审批挂起状态 SHALL 在进程重启后仍可恢复。

#### Scenario: 审批挂起
- **WHEN** `SQL_HARD_GUARD` 判定需要审批
- **THEN** 图在 `approval_node` 处 `interrupt` 挂起，状态写入 checkpointer，接口返回 `WAITING_APPROVAL`

#### Scenario: 审批通过后恢复
- **WHEN** 调用 `resume_graph(run_id, True)`
- **THEN** 从挂起节点继续执行 `SQL_EXECUTE`，且 `approval_status=approved` 使 `allow_high_risk=true`，不重新生成 SQL

#### Scenario: 审批拒绝
- **WHEN** 调用 `resume_graph(run_id, False)`
- **THEN** 图返回拒绝报告，且不再执行 SQL

### Requirement: 审批后不重新生成 SQL
审批通过后 SHALL 复用同一条 SQL 完成执行；任何后续失败 SHALL 直接进入 ANSWER，不得回退到 `SQL_GENERATE`。

#### Scenario: 审批后执行失败不回生成
- **WHEN** 审批通过后 `SQL_VALIDATE` 或 `SQL_SOFT_DQ` 失败
- **THEN** 图直接进入 `ANSWER` 并返回错误报告，`sql_attempts` 不新增

### Requirement: 对外 facade 保持稳定
编排层 SHALL 保留 `run_chatbi_graph(state)` 与 `resume_graph(run_id, approved)` 两个 facade，供 `routes.py`、测试与 eval runner 调用。

#### Scenario: facade 语义不变
- **WHEN** 测试或 eval runner 调用 `run_chatbi_graph`
- **THEN** 返回与迁移前一致的 `DataAgentState`（含 `final_report`）

### Requirement: Checkpoint 不使用进程内存储
审批 checkpoint SHALL 使用持久化存储（`SqliteSaver` 或后续 Postgres），不得使用进程内内存字典。

#### Scenario: 重启后恢复
- **WHEN** 进程重启后调用 `resume_graph(run_id, True)`
- **THEN** 能通过持久化 checkpointer 恢复状态并继续执行
