# ChatBI 主链路

## Purpose

ChatBI 主链路能力：单一主图、Python 唯一编排、Java 平台治理，移除模板匹配与 RAG 支撑设施，审批契约统一。

## Requirements

### Requirement: 单一 ChatBI 主线
系统 SHALL 只提供 ChatBI 主图（ROUTER → SCHEMA → SQL_GENERATE → SQL_HARD_GUARD → SQL_EXECUTE → SQL_VALIDATE → SQL_SOFT_DQ → ANSWER），不得暴露 RAG/归因/DBQA 等全量图分支。

#### Scenario: 请求只走 chatbi 主图
- **WHEN** 客户端调用 Python `/analyze` 且不传 `graphMode`（或传 `chatbi`）
- **THEN** 引擎只执行 chatbi 主图节点，状态中不出现 `rag_result`、`cross_validation`、`insight_report`、`dbqa_*` 字段

#### Scenario: full 模式不再可用
- **WHEN** 客户端调用 Python `/analyze` 并传入 `graphMode=full`
- **THEN** 引擎忽略该模式并按 chatbi 主图执行（或返回参数不支持的错误），不得执行全量图

### Requirement: Python 是唯一的编排实现
系统 SHALL 只保留 Python Agent Engine 作为编排层；Java 侧不得保留任何 agent 编排入口（如 `DataAnalysisAgent`/`CoordinatorAgent` 及其 HTTP 端点）。

#### Scenario: 对外分析接口只走 LangGraph
- **WHEN** 客户端调用 `GET /api/agent/analyze`
- **THEN** 平台层只转发给 Python `/analyze`（`engine=langgraph`），不经过 Java 旧 agent 链路

#### Scenario: 旧对话/流式端点下线
- **WHEN** 客户端调用 `/api/agent/chat` 或 `/api/agent/analyze-stream`
- **THEN** 平台返回 404（端点已移除）

### Requirement: Java 仅提供平台治理能力
平台层 SHALL 保留 SQL 校验、SQL 执行、DQ 审核、审计、Run Trace、审批与（后续）指标字典接口，并 SHALL 移除 RAG/交叉验证相关内部接口。

#### Scenario: 治理接口可用
- **WHEN** 客户端调用 `/internal/sql/validate`、`/internal/sql/execute`、`/internal/dq/sql-result/check`
- **THEN** 返回结构化结果且行为不变

#### Scenario: RAG 内部接口下线
- **WHEN** 客户端调用 `/internal/rag/*` 或 `/internal/cross-validation/*`
- **THEN** 平台返回 404（已移除）

### Requirement: 模板匹配与 RAG 支撑设施移除
系统 SHALL 移除 `sql-templates.yml`/`SqlTemplateMatcher`、向量库（Ollama embedding）配置及 `comment_content` 评论种子数据。

#### Scenario: 模板匹配不再参与
- **WHEN** 引擎执行 SQL 生成
- **THEN** 不存在"命中模板零 LLM 调用"的路径，SQL 统一由生成节点产出

#### Scenario: RAG 数据不再注入
- **WHEN** 运行数据初始化
- **THEN** 不创建 `comment_content` 表、不写入评论数据、不加载向量库、不设置 `content_dim.ad_count/ad_positions`

### Requirement: 审批接口契约统一
系统 SHALL 将高风险 SQL 审批统一为 `POST /api/agent/runs/{runId}/approval`（Java 侧）与 `POST /runs/{runId}/approval`（Python 侧），文档不得再描述不存在的 `/runs/{runId}/resume`。

#### Scenario: 审批路径一致
- **WHEN** 联调手册或接口契约描述审批流程
- **THEN** 文档中的路径与实现完全一致，且不出现 `/runs/{runId}/resume`
