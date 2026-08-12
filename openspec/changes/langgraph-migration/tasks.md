## 1. 依赖与 spike

- [x] 1.1 更新 `agent-engine/pyproject.toml`：`langgraph>=1.2,<2` + `langgraph-checkpoint-sqlite>=2.0.4`
- [x] 1.2 写最小 spike（compile + interrupt + SqliteSaver + resume），验证版本 API 签名

## 2. 图重写

- [x] 2.1 用 `StateGraph` 重写 `graph_builder.py`：注册 8 个 chatbi 节点 + `approval_node`
- [x] 2.2 实现条件边：hard_guard → (approval_node | sql_generate 回环 | sql_execute)；validate/dq → (sql_generate 回环 | answer)；approval → (sql_execute | answer)
- [x] 2.3 新增 `approval_node`：`interrupt({sql, approvalReasons, runId})`，恢复值决定 approved/rejected
- [x] 2.4 审批后失败不回生成：`validate/dq` 失败且 `approval_status=approved` → 直接 ANSWER
- [x] 2.5 保留 `traced_node` 回写：以 `traced(name)` 装饰器包节点

## 3. Checkpoint 与 facade

- [x] 3.1 删除 `checkpoints.py` 的 `InMemoryCheckpointStore`，接入 `SqliteSaver`（文件路径加入 `.gitignore`）
- [x] 3.2 保留 facade：`run_chatbi_graph(state)` 内部 `ainvoke(config={"thread_id": run_id})`；`resume_graph(run_id, approved)` 内部 `ainvoke(Command(resume=approved), ...)`
- [x] 3.3 更新 `routes.py`：`thread_id=run_id` 映射；WAITING_APPROVAL 判定不变

## 4. 测试与验证

- [x] 4.1 适配现有 `tests/test_graph_flow.py`（17 个用例）到新 facade
- [x] 4.2 新增：审批挂起返回 WAITING_APPROVAL；`resume_graph(True)` 复用同 SQL 且 `allow_high_risk=true`；`resume_graph(False)` 返回拒绝报告；重启后（新 checkpointer 实例）可恢复
- [x] 4.3 `pytest tests`、`ruff check app tests`、`python -m app.eval.runner --mode mock` 全绿
- [x] 4.4 更新 `agent-engine/README.md` 与文档中编排章节（LangGraph 化后的结构）
