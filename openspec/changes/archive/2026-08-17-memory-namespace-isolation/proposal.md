## Why

semantic-memory 落地后发现两个跨进程限制（root cause = eval runner 与 agent-engine 服务器是两个进程，记忆状态不同步）：
1. **real 模式反例 seeding 写错 store**：`run_counterexample` 把反例预置写入 runner 本地 store，但 real 模式的 /analyze 走服务器进程、查的是服务器 store → c25 变相空测（metrics 一致性保护只有单测覆盖，eval 级集成路径未走通）。
2. **--memory on 全量评测无自隔离**：需服务端独立 `MEMORY_DB_PATH` + 跑前手动删库；若直接跑会读真实记忆并污染真实 `memory.sqlite`（golden cases 写进真实记忆）。

## What Changes

- **MemoryStore 支持 namespace**：表加 `namespace` 列，唯一键 `(norm_question, namespace)`；upsert/find/all/delete/record_hit 按 namespace；存量数据默认归 `"default"`。
- **服务器记忆控制 API（agent-engine 内部端点）**：`POST /internal/memory/seed`、`POST /internal/memory/clear`、`GET /internal/memory/entries?namespace=`——让 runner 能直接操控服务器进程的记忆（反例预置 + 评测隔离）。
- **/analyze 请求与 graph state 增加 `memory_namespace`**（默认 `"default"`）：语义解析读路径与写钩子按 namespace 读写，eval 用独立 namespace 与真实记忆完全隔离。
- **eval runner**：`--memory on` 使用独立 eval namespace（per-eval，如 `eval-2026-08-17-<ts>`）；反例通过 `POST /internal/memory/seed` 预置到 eval namespace（real 模式）；启动时 `POST /internal/memory/clear` 清空 eval namespace（自隔离，替代手动删库）。
- **评测验证**：全量 `--memory on` 自隔离跑通（重复对、真反例、命中率、不回退）；`--memory off` 回归不回退；default 记忆不受 eval 污染。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `semantic-resolution`: 「语义记忆检索与写入」需求补 namespace 场景（按 namespace 读写、默认 default、eval 隔离）。
- `agent-eval`: 「记忆行为评测」需求补自隔离场景（eval namespace、seed/clear API、default 不受污染）。

## Impact

- **Python**：`app/memory/store.py`（namespace 列/复合键）、`app/api/routes.py` + `schemas.py`（seed/clear/entries 端点 + memoryNamespace 请求字段）、`app/graph/state.py`（memory_namespace）、`app/graph/nodes.py`（读路径/写钩子按 namespace）、`app/eval/runner.py`（eval namespace + seed/clear 调用）、`app/eval/runner.py`（run_real_case 透传）、`app/memory/retriever.py`（search 按 namespace）。
- **Java**：`AgentController.analyze`（@RequestParam memoryNamespace）、`EngineAnalyzeRequest`（加字段）、`LangGraphClient`（透传）——real 模式全链路透传。
- **评测**：`docs/eval-report.md`（重跑快照）、`docs/开发日志.md`。
- **验证**：Python pytest + ruff、Java mvn test、真实评测。
- **非目标**：向量检索、指标别名/用户偏好、多租户认证、记忆淘汰策略。

