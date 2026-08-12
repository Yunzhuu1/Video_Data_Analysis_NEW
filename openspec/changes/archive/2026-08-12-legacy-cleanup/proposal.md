## Why

仓库里混着三条历史线——旧 Java 多智能体链路、RAG/归因全量图、ChatBI 主线。前两条与既定方向（语义层 + 评测 harness + LangGraph 编排、Java 只做平台治理）冲突，导致文档描述的结构与真实代码严重漂移（例如 `LangGraphAgentEngine设计.md` 承诺的 `edges.py`/`router_agent.py` 等文件并不存在），也增加了简历叙事被追问"为什么有两套实现"的风险。

## What Changes

- **BREAKING**: 移除 Python 全量图（`graphMode=full`）。删除 `run_graph`、`rag_node`/`cross_validation_node`/`insight_node`/`recommendation_node`/`merge_node`/`dbqa_node` 及 `state.py` 中对应字段；`/analyze` 不再接受 `graphMode=full`，仅保留 chatbi 主图。
- **BREAKING**: 移除 Java 旧多智能体链路及其入口。删除 `DataAnalysisAgent`/`CoordinatorAgent`/`RouterAgent`/`SchemaAgent`/`SQLGenerationAgent`/`RAGAgent`/`InsightAgent`/`RecommendationAgent`/`DbqaAgent`/`CrossValidationService`/`SqlExecutionTool`/`MetricQueryTool`/`SqlTemplateMatcher`/`RedisChatMemoryRepository`/`ChatMemoryConfig`/`AgentModelConfig`/`SemanticCacheService`；`/api/agent/analyze` 仅保留 `engine=langgraph` 路径，移除 `/api/agent/chat`、`/api/agent/analyze-stream`、`/api/agent/jiegouhua/stats`。
- 移除 RAG/归因相关数据与配置：`comment_content` 种子与向量库加载、Ollama embedding 配置、`content_dim.ad_count/ad_positions`、`activity_dim`、`dashboard.html` 的归因/评论 tab。
- 移除 `sql-templates.yml` 与 `SqlTemplateMatcher`（模板匹配与未来确定性合成方向重叠且含语法缺陷）。
- 对齐接口契约：审批接口统一为 `POST /api/agent/runs/{runId}/approval`，删除 `服务接口契约.md` 中不存在的 `/runs/{runId}/resume`、`POST /api/analyze` 等旧契约。
- 重排文档主线：更新 `AGENTS.md`/`README.md`，重写 `EVALUATION.md`，将 `DataAgent总体架构.md` 与 `LangGraphAgentEngine设计.md` 合并重写为一份真实结构文档，归档旧设计段落。

## Capabilities

### New Capabilities
- `chatbi-mainline`: 定义唯一的 ChatBI 主线——Python LangGraph 编排 + Java 平台治理；系统不暴露 full 图、不保留 Java agent 入口、不保留 RAG/DBQA 分支。

### Modified Capabilities
<!-- 无既有 spec 需要修改（openspec/specs/ 当前为空） -->

## Impact

- 代码：`agent-engine/app/graph/*`、`agent-engine/app/api/routes.py`、`agent-engine/app/graph/state.py`、`src/main/java/com/yunzhu/video_data_analysis/{agent,controller,service,tool,config}/*`、`src/main/resources/{sql-templates.yml,application.yml,static/dashboard.html}`
- 数据：`DataInitializer` 中 RAG/归因相关种子与建表
- 文档：`AGENTS.md`、`README.md`、`EVALUATION.md`、`docs/*.md`
- API：`/api/agent/*` 对外接口、Python `/analyze` 的 `graphMode` 参数
