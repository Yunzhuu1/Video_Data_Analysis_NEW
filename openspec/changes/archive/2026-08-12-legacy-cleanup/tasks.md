## 1. Python 侧清理（全量图下线）

- [x] 1.1 删除 `agent-engine/app/graph/nodes.py` 中 `rag_node`、`cross_validation_node`、`insight_node`、`recommendation_node`、`merge_node`、`dbqa_node`
- [x] 1.2 删除 `agent-engine/app/graph/graph_builder.py` 中 `run_graph` 与 `resume_graph` 的 full 分支，仅保留 `run_chatbi_graph` 与 chatbi 恢复路径
- [x] 1.3 删除 `agent-engine/app/graph/state.py` 中 `rag_result`、`cross_validation`、`insight_report`、`recommendations`、`dbqa_*` 字段
- [x] 1.4 更新 `agent-engine/app/api/routes.py` 与 `schemas.py`：`graph_mode` 仅接受 `chatbi`（或忽略并默认 chatbi）
- [x] 1.5 更新 `agent-engine/tests/test_graph_flow.py`：删除 full 图相关测试，补齐 chatbi-only 断言

## 2. Java 侧清理（旧 agent 链路下线）

- [x] 2.1 删除 `src/main/java/com/yunzhu/video_data_analysis/agent/` 下旧 agent 类（DataAnalysisAgent、CoordinatorAgent、RouterAgent、SchemaAgent、SQLGenerationAgent、RAGAgent、InsightAgent、RecommendationAgent、DbqaAgent）
- [x] 2.2 删除 `CrossValidationService`、`SqlExecutionTool`、`MetricQueryTool`、`SqlTemplateMatcher`、`RedisChatMemoryRepository`、`ChatMemoryConfig`、`AgentModelConfig`、`SemanticCacheService`
- [x] 2.3 精简 `AgentController`：`/api/agent/analyze` 仅保留 langgraph 路径；删除 `/chat`、`/analyze-stream`、`/jiegouhua/stats`；删除 RAG/交叉验证 controller 与相关 DTO
- [x] 2.4 删除 `src/main/resources/sql-templates.yml` 与 `application.yml` 中 vectorstore/embedding/Ollama 配置段
- [x] 2.5 更新 `src/test/java` 中引用被删类的测试；`mvn test` 全绿

## 3. 数据与前端清理

- [x] 3.1 `DataInitializer` 删除 `comment_content` 建表/种子、向量库加载、`ad_count/ad_positions` 扩展；保留 `user_behavior_fact`/`activity_dim` 表结构
- [x] 3.2 删除 `VectorStoreConfig` 及无用依赖引用
- [x] 3.3 `dashboard.html` 移除"交叉验证归因/检索用户评论"tab 与相关进度映射

## 4. 契约与文档主线重排

- [x] 4.1 重写 `docs/服务接口契约.md`：仅保留真实端点；删除 `/runs/{runId}/resume`、`POST /api/analyze` 旧契约；审批路径对齐实现
- [x] 4.2 将 `docs/DataAgent总体架构与迁移路线.md` 与 `docs/LangGraphAgentEngine设计.md` 合并重写为一份"Agent 编排与架构设计"文档（只描述真实结构 + 新主线）；旧段落移入 `docs/archive/`
- [x] 4.3 更新 `AGENTS.md` 与 `README.md`：删除 RAG/归因/DBQA"后续扩展"表述，对齐 chatbi-only 主线
- [x] 4.4 更新 `EVALUATION.md` 与 `docs/开发规范.md`：删除 RAG/DBQA 相关指标与测试要求

## 5. 验证

- [x] 5.1 `mvn test`、`pytest tests`、`ruff check app tests` 全部通过
- [x] 5.2 手工验证：`/api/agent/analyze`（langgraph）正常返回；full/旧端点返回 404；审批路径按契约工作
