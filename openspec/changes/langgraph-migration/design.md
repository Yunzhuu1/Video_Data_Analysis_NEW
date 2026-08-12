## Context

编排层现状：`graph_builder.py` 用三个复制粘贴的 while 循环（`run_chatbi_graph`/`run_graph`/`resume_graph`）实现控制流；重试逻辑散落在 `if/continue`；HITL 靠 `InMemoryCheckpointStore` 保存状态。`legacy-cleanup` 已先行移除 full 图，因此本次迁移只针对 chatbi 单图。

## Goals / Non-Goals

**Goals:**
- 用真 LangGraph（`StateGraph` + 条件边 + `interrupt` + 持久化 checkpointer）重写编排层。
- 审批跨进程/重启可恢复；恢复后不重复副作用。
- 对外 facade（`run_chatbi_graph`/`resume_graph`）与运行语义保持不变，测试与 eval runner 改动最小。

**Non-Goals:**
- 不引入语义解析/确定性合成（由 `semantic-resolve-node` 承接）。
- 不新增节点能力，仅迁移现有 8 节点 chatbi 图。
- 不接 LangSmith 等外部可观测平台（留给后续）。

## Decisions

- **决策 1：节点保持"纯函数 + 装饰器回写"**。`sql_hard_guard_node` 等保持无副作用（只算状态），Run Trace 回写通过 `traced(name)` 装饰器包一层（内部仍调 `platform.start_node/finish_node/fail_node`），避免 `interrupt` 打断回写逻辑。
- **决策 2：interrupt 放独立 `approval_node`**。hard_guard 判定 `approval_status=waiting` 后由边进入 `approval_node`，该节点调用 `interrupt({sql, approvalReasons, runId})` 挂起；恢复时 `Command(resume=True/False)` 返回值决定 `approved/rejected`。理由：hard_guard 保持可单测，interrupt 语义集中一处。替代方案（hard_guard 内直接 interrupt）被否：破坏节点纯度。
- **决策 3：审批后禁止回生成节点**。`validate/dq` 失败且 `approval_status=approved` 时直接走 ANSWER，不回 SQL_GENERATE——保留"审批对象防漂移"（审批过的 SQL 不被重新生成替换）。这是现有设计最值钱的语义，边逻辑必须显式表达。
- **决策 4：checkpointer 选 `SqliteSaver`**（`langgraph-checkpoint-sqlite`，aiosqlite 异步支持）。理由：跨进程/重启可恢复、零额外基础设施。替代方案：`MemorySaver`（仍是进程内，未解决问题）、`PostgresSaver`（生产级但需新增 PG 服务，留待后续）。
- **决策 5：保留 facade，API 面稳定**。`run_chatbi_graph(state)` 内部 `compiled.ainvoke(state, config={"thread_id": run_id})`；`resume_graph(run_id, approved)` 内部 `compiled.ainvoke(Command(resume=approved), config=...)`。理由：`routes.py`、测试、eval runner 改动趋近于零。
- **决策 6：state 增量 + reducer 作为可迭代演进**。本次先让节点返回全量 state（最小改造、语义不变），`sql_attempts`/`warnings`/`errors` 的 reducer 化列为后续任务；避免一次迁移混入大规模重构。
- **决策 7：版本钉死**。`langgraph>=1.2,<2` + `langgraph-checkpoint-sqlite>=2.0.4`；规避 PYSEC-2026-83（1.0.9 及以前的 msgpack checkpoint 反序列化问题）。注意 `recursion_limit` 默认 25 足够容纳现有重试环（最多 3 次/阶段），但保留显式上限断言。

## Risks / Trade-offs

- [LangGraph 版本 API 漂移（interrupt/Command/checkpointer 签名）] → 钉版本后先写一个最小 spike（compile + interrupt + resume）验证签名，再动主代码。
- [SqliteSaver 连接生命周期与 FastAPI 冲突] → 在应用启动时创建并在进程生命周期内复用；文档说明单实例适用、多实例需 Postgres。
- [恢复时节点重跑导致副作用重复（trace 回写、SQL 执行）] → 回写接口按 nodeId 幂等；SQL 执行由 runId 幂等；在 `approval_node` 之后不做重复生成（见决策 3）。
- [测试改造量大] → 保持 facade 后，现有 17 个测试仅需适配返回方式；新增 interrupt/resume 专项测试。

## Migration Plan

1. 写 spike：最小 StateGraph + interrupt + SqliteSaver，验证版本 API。
2. 重写 `graph_builder.py`：节点注册 + 条件边 + `approval_node` + 编译。
3. 替换 `checkpoints.py`：删除 `InMemoryCheckpointStore`，接入 `SqliteSaver`。
4. 调整 facade 与 `routes.py`（`thread_id=run_id` 映射）。
5. 更新测试：适配 facade；新增审批挂起/恢复/拒绝用例。
6. 全量验证：`pytest` + `ruff` + mock eval。

## Open Questions

- 是否在本次就引入 `Annotated` reducer（决策 6 默认延后）。
- `SqliteSaver` 文件路径是否放 `agent-engine/checkpoints.sqlite` 并加入 `.gitignore`（默认是）。
