# DataAgent 总体架构与迁移路线

## 1. 背景

当前项目已经具备一个可演示的 Spring Boot + Spring AI 多 Agent 数据分析链路：

```text
DataAnalysisAgent
  -> RouterAgent
  -> CoordinatorAgent
       -> SchemaAgent
       -> SQLGenerationAgent
       -> Execution Guidance
       -> RAGAgent
       -> CrossValidation
       -> InsightAgent + RecommendationAgent
       -> DBQA
```

它的优势是业务链路完整、SQL 安全意识较强、RAG 归因和报告质检已经有雏形。

但如果目标是做一个简历上更有含金量的企业级 DataAgent，需要从“一次性 Agent 调用链”升级为：

```text
Spring Boot 企业平台层 + Python LangGraph Agent 编排引擎
```

两者的职责边界如下：

| 层 | 主要职责 | 技术栈 |
|---|---|---|
| 平台层 | API、权限、审计、SQL 安全执行、指标治理、Run Trace、缓存、运维接口 | Spring Boot |
| Agent 引擎层 | 状态机编排、条件分支、SQL 自修复、RAG 决策、DBQA 循环、人工审批、Checkpoint | Python + LangGraph |
| 数据与基础设施 | MySQL、Redis VectorStore、Ollama embedding、模型 API | Docker Compose |
| 前端层 | 分析入口、Agent DAG、运行详情、评测报告、运维看板 | 可选 React/Vue |

## 2. 目标架构

```text
用户 / Dashboard
      |
      v
Spring Boot Platform
  - /api/analyze
  - /api/runs/{runId}
  - /api/metrics
  - /internal/sql/execute
  - /internal/schema/relevant
  - /internal/runs/{runId}/nodes
      |
      v
Python LangGraph Agent Engine
  - RouterNode
  - SchemaNode
  - SQLGenerateNode
  - SQLExecuteNode
  - SQLValidateNode
  - RAGNode
  - CrossValidationNode
  - InsightNode
  - RecommendationNode
  - DBQANode
  - HumanApprovalNode
      |
      v
Spring Boot Internal Services
  - SqlExecutionService
  - MetricCatalogService
  - SchemaCatalogService
  - AgentRunTraceService
  - AuditLogService
```

### 2.1 请求主链路

```text
1. 用户调用 Spring Boot /api/analyze
2. Spring Boot 创建 run_id，写入 agent_run
3. Spring Boot 调用 Python /analyze，传入 run_id、user_id、question
4. LangGraph 执行 Agent 状态图
5. 每个节点开始/结束时回写 Spring Boot Run Trace
6. SQL 查询统一调用 Spring Boot /internal/sql/execute
7. Spring Boot 做 SQL 校验、权限、审计、执行和缓存
8. LangGraph 汇总最终报告
9. Spring Boot 持久化 final_report 并返回用户
```

### 2.2 核心原则

1. **Agent 不直连数据库**
   所有 SQL 执行必须经过 Spring Boot SQL Gateway，统一校验、审计、限流和缓存。

2. **LangGraph 只负责编排，不负责企业治理**
   权限、脱敏、审计、指标字典、SQL 风险控制属于平台层。

3. **所有节点必须状态化**
   每个节点必须有 `PENDING/RUNNING/SUCCESS/FAILED/SKIPPED/WAITING_APPROVAL` 状态。

4. **所有跨服务通信必须结构化**
   禁止用自由文本传递关键状态，例如 SQL 执行结果、RAG 结果、DBQA 结果。

5. **先兼容旧链路，再逐步替换**
   Spring AI 旧链路可保留为 fallback，LangGraph 稳定后再下线旧 Coordinator。

## 3. 推荐目录结构

```text
video_data_analysis/
├── backend-platform/
│   └── Spring Boot 平台层
├── agent-engine/
│   └── Python LangGraph Agent 引擎
├── frontend-dashboard/
│   └── 可选前端
├── infra/
│   └── docker-compose、MySQL、Redis、Nginx
├── docs/
│   └── 架构、设计、规范、评测报告
└── scripts/
    └── 启动、评测、造数脚本
```

当前仓库还没有拆成 monorepo。迁移时可以先在现有根目录下新增 `agent-engine/`，Spring Boot 代码暂时保留在 `src/`，等稳定后再移动到 `backend-platform/`。

## 4. 迁移阶段

### 阶段 1：Spring Boot 平台层基线

目标：让现有项目先具备企业平台基础。

已完成：

- 移除主配置硬编码密钥。
- 新增 `dev/test/prod` profile。
- 测试环境关闭数据初始化和慢查询建表。
- `mvn test` 通过。

下一步：

- 新增 `agent_run`、`agent_run_node`。
- 新增 `AgentRunTraceService`。
- 新增 `AgentRunQueryService`。
- 新增 `/api/runs` 和 `/api/runs/{runId}`。

### 阶段 2：SQL Gateway 化

目标：把 `SqlExecutionTool` 拆成平台服务。

新增：

```text
SqlExecutionService
SqlExecuteRequest
SqlExecuteResult
SqlPlanAnalyzer
SqlAuditService
```

旧的 `SqlExecutionTool.executeSql(sql)` 保留，但内部调用 `SqlExecutionService`。

验收：

- SQL 执行结果结构化。
- 并发请求不会串 SQL。
- 危险 SQL 拦截率 100%。
- 每次 SQL 执行都写审计日志。

### 阶段 3：LangGraph 服务骨架

目标：新增 Python 服务并和 Spring Boot 打通。

第一版图：

```text
START -> EchoNode -> END
```

Spring Boot `/api/analyze` 先转发到 Python `/analyze`，Python 返回固定结构化报告。

验收：

- 双服务能一起启动。
- `run_id` 能从 Spring Boot 传到 LangGraph。
- LangGraph 节点状态能回写 Spring Boot。

### 阶段 4：迁移 Agent 节点

迁移顺序：

```text
RouterNode
SchemaNode
SQLGenerateNode
SQLExecuteNode
SQLValidateNode
RAGNode
CrossValidationNode
InsightNode
RecommendationNode
DBQANode
HumanApprovalNode
```

不要一次迁完。每迁一个节点，都要保证：

- 节点输入输出结构化。
- 节点状态写入 Run Trace。
- 节点失败有明确错误。
- 可独立单测。

### 阶段 5：Human-in-the-loop 与 Checkpoint

目标：体现 LangGraph 的核心价值。

高风险 SQL 触发条件：

- 访问明细表。
- 访问敏感字段。
- EXPLAIN rows 超阈值。
- 查询无时间范围。
- 命中高危 SQL 规则。

流程：

```text
SQLRiskCheck -> WAITING_APPROVAL -> APPROVED/REJECTED -> Continue/End
```

### 阶段 6：评测体系

目标：从“能演示”升级到“有指标”。

评测集：

- Text2SQL。
- SQL 安全拦截。
- RAG precision@5。
- 端到端报告质量。
- 延迟和 Token 成本。

输出：

```text
docs/eval-report.md
```

## 5. 最终验收标准

项目完成后，应能现场展示：

1. 输入一个复杂业务问题。
2. 前端显示 Agent DAG 逐步运行。
3. SQL 生成失败后自动修正。
4. 高风险 SQL 进入人工审批。
5. RAG 找到评论证据。
6. 播放明细做交叉验证。
7. DBQA 发现报告缺口并补充查询。
8. 最终生成结构化报告。
9. Run Trace 可回放。
10. Eval 报告展示准确率、耗时、成本。

## 6. 简历定位

推荐项目标题：

```text
企业级 DataAgent 数据分析平台
```

推荐描述：

```text
基于 Spring Boot + LangGraph 设计并实现企业级 DataAgent 平台。Spring Boot 提供 SQL 安全执行、指标治理、权限审计、Run Trace 和运维 API；LangGraph 提供可恢复多 Agent 状态机，实现 Text2SQL 自修复、RAG 评论归因、播放行为交叉验证、Human-in-the-loop 高风险 SQL 审批和 DBQA 报告质检，并通过自动评测体系量化 SQL 正确率、RAG precision@5、端到端报告质量和 Token 成本。
```
