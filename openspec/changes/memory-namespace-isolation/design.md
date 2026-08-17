## Context

semantic-memory 已落地：MemoryStore（aiosqlite）+ TextSimilarityRetriever + 缓存直通/few-shot 注入 + --memory 评测。两个跨进程限制根因相同：**eval runner 与服务器是两个进程，记忆状态不同步**。

## Goals / Non-Goals

**Goals：** eval 记忆与真实记忆完全隔离（namespace）；反例预置走服务器 API（真验证）；全量 --memory on 评测自包含、无需 env/重启；default 记忆不受污染。
**Non-Goals：** 向量检索、指标别名/用户偏好、多租户认证、记忆淘汰。

## Decisions

### D1：MemoryStore namespace（复合唯一键）
- 表加 `namespace TEXT NOT NULL DEFAULT 'default'`，唯一索引 `(norm_question, namespace)`（替代单列 norm 唯一）。
- upsert/find/all/delete/record_hit 增加 `namespace` 参数（默认 "default"）；`find_by_question(norm, namespace)`。
- 存量数据迁移：`ALTER TABLE` 加列 + 默认值即可，现有行归 "default"（无数据丢失，schema 简单）。
- 备选：按 namespace 分表 → 拒绝，单表 + 复合键更简单、迁移成本低。

### D2：服务器记忆控制 API（内部端点）
- `POST /internal/memory/seed`：body `{namespace, question, intent, metric_codes}` → `store.upsert`（按 namespace）。**拒绝写入 `default` namespace（P2，安全加固）**：生产记忆只能由写钩子沉淀（它有全链路成功门槛）；seed 仅允许非 default/eval namespace。intent 做 pydantic 校验（结构合法才接受）。
- `POST /internal/memory/clear`：body `{namespace}` → 删除该 namespace 全部条目。**幂等（P3）**：namespace 不存在也返回成功，避免 runner 启动竞态。
- `GET /internal/memory/entries?namespace=`：返回该 namespace 条目列表。**用途仅评测验证/调试，不参与运行时读路径**（防未来被业务读路径依赖）。
- **鉴权边界**：与现有 internal 端点一致，校验 `X-Internal-Token`（`settings.internal_api_token`）；仅 localhost 部署，不暴露公网。
- 这些端点打服务器的 `nodes.memory`——与真实读写同一 store，解决"runner 写错 store"的根因。

### D3：/analyze 请求 + graph state 的 memory_namespace
- `AnalyzeRequest` 增加 `memoryNamespace`（默认 "default"）；`routes.py` 透传到 `run_chatbi_graph` 初始 state。
- `DataAgentState` 增加 `memory_namespace: str`（默认 "default"）。
- `semantic_resolve_node` 的 `_memory_pre_resolve` 与 `_memory_write_hook` 按 `state["memory_namespace"]` 读写。
- **Java 透传链（P1-1，必修）**：real 模式调用链 = runner → Spring `/api/agent/analyze` → `LangGraphClient` → Python `/analyze`。Spring 端必须透传 memoryNamespace，三处：
  1. `AgentController.analyze` 增加 `@RequestParam(defaultValue="default") String memoryNamespace`；
  2. `EngineAnalyzeRequest` 增加 `memoryNamespace` 字段；
  3. `LangGraphClient.analyze` 构造请求时透传。
  约 10 行 + mvn test；`Impact` 补 Java。

### D4：eval runner 自隔离
- `--memory on`：生成 **per-eval namespace**：`eval_namespace = f"eval-{eval_date}-{start_ts}"`（一次评测一个 namespace，天然唯一，无需清理）。**粒度定为 per-eval（非 per-case）**：mock 的 run_id 是 per-case、real 是 per-request uuid，per-case 会让 seed 目标不明确；per-eval 下所有用例/seed/clear 共享同一 namespace，用例间问题互不相似、实际无害。
- 启动时：real 模式 `POST /internal/memory/clear {namespace=eval_namespace}`（自清理，替代手动删库）；mock 模式清本地 store 对应 namespace。
- `run_counterexample`：real 模式 `POST /internal/memory/seed` 到 eval namespace（服务器 store）；mock 模式写本地 nodes.memory（同进程）。
- **反例重定义为"毒化变体"（P2）**：原"播放量 vs 点赞量"相似度≈0.91 走 inject 分支，根本没触发 metrics 一致性校验（测的是阈值不是校验）。改为：seed `{question:"最近7天点赞量是多少", intent:{metrics:[total_plays]}}`（文本与 intent 不一致的毒条目），查询同文本（相似度 1.0 → 直通候选）→ **metrics 一致性校验必须拦截**（band != hit）。一个用例同时验证 metrics 校验路径与 seed 毒化防护。
- `run_real_case`/`run_graph_case`：/analyze 请求带 `memoryNamespace=eval_namespace`（real）；graph 初始 state 带（mock）。
- 评测结束可选 `POST clear` 清理 eval namespace（MVP 可不做，namespace 独立即可）。

### D5：mock/real 行为统一
- mock 模式（runner 与图同进程）：namespace 走本地 store，seed/clear 直接调 `nodes.memory`。
- real 模式（跨进程）：namespace 走服务器 store，seed/clear 走 `/internal/memory/*` API。
- 两者语义一致：**读路径按 state 的 memory_namespace，写钩子按 state 的 memory_namespace**，runner 侧只是"如何触达 store"不同。

## Risks / Trade-offs

- [存量 memory.sqlite 迁移] → ALTER TABLE 加列 + 默认值，无数据丢失；迁移脚本进 change。
- [seed/clear 端点被滥用] → 内部 token 校验 + localhost 部署边界（与现有 internal 端点一致）。
- [namespace 透传链遗漏某处] → 单测覆盖：读路径/写钩子/run_real_case 均按 namespace；集成冒烟验证 eval 与 default 互不污染。
- [Java 透传遗漏] → 三处透传（AgentController/EngineAnalyzeRequest/LangGraphClient）+ tasks 2.5 Java 测试覆盖

## Migration Plan

1. MemoryStore namespace 列 + 复合键 + 存量迁移（单测）。
2. seed/clear/entries 端点 + 鉴权（单测）。
3. /analyze + graph state 透传 memory_namespace；读路径/写钩子按 namespace（单测）。
4. runner：eval namespace + seed/clear 调用 + run_real_case 透传（单测 + 聚焦冒烟）。
5. 全量评测：--memory on 自隔离重跑（重复对/反例/命中率/不回退/default 不污染）+ --memory off 回归 + 文档。
