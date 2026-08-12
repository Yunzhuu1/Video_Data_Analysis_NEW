## Why

编排层当前是手写 while 循环状态机（`graph_builder.py`），文档与依赖声明 LangGraph 但代码零 `from langgraph` 导入；HITL 审批依赖进程内内存 checkpoint（`InMemoryCheckpointStore`），重启即丢。迁移到真 LangGraph 能让控制流显式化（节点/条件边）、审批持久化（checkpointer + interrupt），并让"LangGraph 编排"的简历表述变得真实。

## What Changes

- 用 `langgraph.graph.StateGraph` 重写 `graph_builder.py`：节点 + 条件边（hard_guard/validate/dq 失败重试回环、审批分支）。
- 审批改为 LangGraph `interrupt()` + 持久化 checkpointer（`langgraph-checkpoint-sqlite` 的 `SqliteSaver`）；`resume_graph` 改为内部调用 `Command(resume=...)`。
- 保留 facade `run_chatbi_graph(state)` / `resume_graph(run_id, approved)`，使 `routes.py`、测试、eval runner 改动最小。
- `state.py` 为 `sql_attempts`/`warnings`/`errors` 引入 reducer（`Annotated[list, operator.add]`），节点改为返回增量（可迭代演进，不阻塞本次迁移）。
- 删除 `InMemoryCheckpointStore`；保留 `traced_node` 的 Run Trace 回写（以节点装饰器形式接入）。
- `pyproject.toml` 钉死 LangGraph 版本（>=1.2，避开 PYSEC-2026-83 涉及的 1.0.9 及以前），新增 `langgraph-checkpoint-sqlite`。

## Capabilities

### New Capabilities
- `langgraph-orchestration`: 编排层基于真 LangGraph 状态图：显式节点与条件边、持久化 checkpoint、interrupt 式 HITL、恢复不重复副作用。

### Modified Capabilities
<!-- 无既有 spec 需要修改 -->

## Impact

- 代码：`agent-engine/app/graph/{graph_builder,state,checkpoints,nodes}.py`、`agent-engine/app/api/routes.py`
- 依赖：`agent-engine/pyproject.toml`
- 测试：`agent-engine/tests/test_graph_flow.py`（新增 interrupt/resume 用例）
- 文档：`docs/LangGraphAgentEngine设计.md`（合并重写后文档）中的编排章节
