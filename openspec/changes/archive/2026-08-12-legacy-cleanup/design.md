## Context

项目当前是双服务架构：Spring Boot 平台层 + Python Agent Engine。代码中保留了三套历史实现：Java 旧多智能体链路（Spring AI ChatClient 手写编排）、Python 全量图（RAG/归因/DBQA 占位节点）、以及真正的 ChatBI 主线。文档与实现严重漂移（如 `LangGraphAgentEngine设计.md` 描述了不存在的 `edges.py`、`router_agent.py` 等）。

新方向已确定：ChatBI 主线 = 语义解析 + 确定性合成 + 安全护栏 + HITL 审批 + 评测 harness；Java 只保留平台治理（SQL 校验/执行/DQ/审计/Run Trace/指标字典）；后续将迁移到真 LangGraph。本次 change 只做"减法"与文档对齐，不引入新功能。

## Goals / Non-Goals

**Goals:**
- 删除全部全量图（RAG/归因/DBQA）代码、数据、配置与文档段落，使 `/analyze` 只存在 chatbi 一条主线。
- 删除 Java 旧多智能体链路及其对外入口，Java 只保留平台治理能力。
- 删除与未来方向冲突的模板匹配（`sql-templates.yml`/`SqlTemplateMatcher`）与 RAG 支撑设施（向量库、Ollama、评论数据）。
- 对齐接口契约（审批路径、`/api/agent/analyze` 契约），重排文档主线。

**Non-Goals:**
- 不实现语义解析/确定性合成（由 `semantic-resolve-node` 承接）。
- 不做 LangGraph 迁移（由 `langgraph-migration` 承接）。
- 不建设评测 harness（由 `agent-eval-harness` 承接）。
- 不重构 SQL 治理逻辑本身（保留 `SqlValidationService`/`SqlExecutionService`/`SqlResultDQService` 等）。

## Decisions

- **决策 1：全量图直接删除，而不是保留为"后续扩展"**。理由：占位节点是硬编码模板输出，保留会让"已实现功能"叙事失真，且与主线共用 `state.py` 造成概念污染。替代方案（feature flag 隔离）被否：多一套代码路径只会延续"文档 vs 代码"漂移。
- **决策 2：Java 旧 agent 链路删除，而不是保留为 fallback**。理由：`AgentController` 当前默认 `engine=spring` 与"langgraph 是主线"矛盾；保留两套实现是面试最大穿帮点。替代方案（标记 deprecated）被否：dead code 仍会被静态扫描/面试追问。
- **决策 3：删除 `SqlTemplateMatcher`/`sql-templates.yml`**。理由：模板匹配与未来"确定性合成"方向重叠但更粗糙（`metric_trend` 模板含重复 `OR date BETWEEN`，`category_metric` 的 `WHERE category '{category}'` 语法可疑）；确定性合成将来在 Python 侧重新设计。
- **决策 4：RAG 支撑设施（向量库/Ollama/comment 数据）一并删除**。理由：它们是全量图的地基；保留会残留无消费者的配置与依赖（`VectorStoreConfig`、embedding 配置）。
- **决策 5：接口契约以真实实现为准**。审批统一为 `POST /api/agent/runs/{runId}/approval`；`/api/agent/analyze` 仅保留 langgraph 路径；删除文档中不存在的 `/runs/{runId}/resume`、`POST /api/analyze`。
- **决策 6：文档采用"重写 + 归档"而非整体删除**。旧设计段落移入 `docs/archive/` 保留历史，主线文档重写为真实结构。

## Risks / Trade-offs

- [删除 Java agent 后 `SqlExecutionService` 仍被 `InternalSqlController` 使用，无影响] → 执行清理前先 grep 依赖，确认无隐藏调用方（如 `DataAnalysisAgent` 对 `SqlExecutionTool` 的引用）。
- [删除 `SemanticCacheService` 可能影响既有测试] → 同步更新 `src/test/java` 中引用旧类的测试，保证 `mvn test` 全绿后提交。
- [删除 `graphMode=full` 为破坏性变更] → README/联调手册同步更新，Python `/analyze` 的 `graph_mode` 字段改为仅接受 `chatbi`（或忽略并默认 chatbi）。
- [文档重排工作量集中在 `LangGraphAgentEngine设计.md`] → 合并重写为单一"Agent 编排设计"文档，只描述真实结构。

## Migration Plan

1. Python 侧删除全量图节点与 `run_graph`/`resume_graph` 的 full 分支，`routes.py` 仅保留 chatbi；同步删 `state.py` 全量图字段。
2. Java 侧删除旧 agent 类与相关 controller 方法/DTO；`AgentController.analyze` 仅走 langgraph；删除 RAG/模板/缓存相关类与配置。
3. 数据初始化去掉 RAG 种子与建表；清理 `dashboard.html` 归因 tab。
4. 对齐接口契约文档与 `docs/*` 主线；归档旧设计段落。
5. 全量跑 `mvn test` + `pytest` + `ruff`，确认绿色后提交。

## Open Questions

- `user_behavior_fact.dimension`（JSON 列）与 `activity_dim` 是否一并删除，还是保留作为 mock 数据供后续语义层使用？默认：保留 `user_behavior_fact`/`activity_dim` 表结构，仅删除 RAG 专属内容（comment/向量/广告字段）。
