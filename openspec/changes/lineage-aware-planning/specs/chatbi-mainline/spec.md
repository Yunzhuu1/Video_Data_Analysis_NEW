## MODIFIED Requirements

### Requirement: 单一 ChatBI 主线
系统 SHALL 只提供 ChatBI 主图（ROUTER → SCHEMA → SEMANTIC_RESOLVE → PLAN_ENUMERATE → 条件式 PLAN_SELECT → PLAN_VALIDATE → SQL_SYNTHESIZE（规划未覆盖/失败走 legacy，合成失败降级 SQL_GENERATE）→ SQL_HARD_GUARD → SQL_EXECUTE → SQL_SOFT_DQ → ANSWER），不得暴露 RAG/归因/DBQA 等全量图分支，且不得存在冗余的 SQL_VALIDATE 节点。PLAN_SELECT 仅在多个合法候选存在真实取舍时调用独立 Planner LLM，规划重选最多一次，不得改变审批恢复路径。

#### Scenario: 请求只走 chatbi 主图
- **WHEN** 客户端调用 Python `/analyze` 且不传 `graphMode`（或传 `chatbi`）
- **THEN** 引擎只执行 chatbi 主图节点，状态中不出现 `rag_result`、`cross_validation`、`insight_report`、`dbqa_*` 字段

#### Scenario: full 模式不再可用
- **WHEN** 客户端调用 Python `/analyze` 并传入 `graphMode=full`
- **THEN** 引擎忽略该模式并按 chatbi 主图执行（或返回参数不支持的错误），不得执行全量图

#### Scenario: 主图不含冗余校验节点
- **WHEN** 引擎构建 chatbi 主图
- **THEN** 图中不存在 `SQL_VALIDATE` 节点；物理 QueryPlan 由 `PLAN_VALIDATE` 校验，SQL 的语法/安全/执行结果仍分别由 `SQL_HARD_GUARD` 与 `SQL_EXECUTE` 承担

#### Scenario: 规划节点不破坏审批恢复
- **WHEN** 已生成 SQL 进入门禁或等待审批恢复
- **THEN** 不重新运行 PLAN_ENUMERATE/PLAN_SELECT，审批通过后继续执行审批时刻的同一条 SQL

