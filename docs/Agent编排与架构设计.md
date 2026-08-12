# Agent 编排与架构设计

> 本文档描述当前真实实现的结构与演进方向。由 `DataAgent总体架构与迁移路线.md` 与 `LangGraphAgentEngine设计.md` 合并重写而来，只保留与实现一致的内容。

## 1. 定位

双服务架构：

- **Spring Boot 平台层**：对外 API、SQL 校验/执行/DQ、审计、Run Trace、审批入口、Schema 缓存、Token 统计。只做确定性平台治理，不做编排。
- **Python Agent Engine**：ChatBI 状态图编排（当前为自研 while-loop 状态机，计划迁移到真 LangGraph）、SQL 生成、失败重试、高风险 SQL 等待审批、最终回答生成。

边界原则：

- Python 不直连数据库；所有 SQL 必须过 Spring Boot 统一入口。
- Java 负责"能不能查、怎么安全查、怎么审计"；Python 负责"怎么编排、下一步走哪"。
- 确定性平台能力下沉 Java；LLM 只做生成与轻量判断。

## 2. 当前主链路（ChatBI）

```text
User -> Spring Boot /api/agent/analyze -> LangGraphClient -> Python /analyze
  -> ROUTER -> SCHEMA -> SQL_GENERATE -> SQL_HARD_GUARD -> SQL_EXECUTE
  -> SQL_VALIDATE -> SQL_SOFT_DQ -> ANSWER
  -> AnalysisReport
```

`graphMode` 仅支持 `chatbi`。全量图（RAG/归因/DBQA）已下线。

## 3. 服务结构（真实）

```text
agent-engine/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── settings.py             # 环境配置
│   ├── api/
│   │   ├── routes.py           # /health /analyze /runs/{id}/approval
│   │   └── schemas.py          # AnalyzeRequest/Response
│   ├── graph/
│   │   ├── state.py            # DataAgentState
│   │   ├── graph_builder.py    # run_chatbi_graph / resume_graph / traced_node
│   │   ├── nodes.py            # chatbi 8 节点
│   │   └── checkpoints.py      # 审批 checkpoint（当前进程内，计划换 SqliteSaver）
│   ├── agents/
│   │   ├── sql_agent.py        # SQL 生成 Agent
│   │   └── answer_agent.py     # 回答生成 Agent
│   ├── clients/
│   │   ├── llm_client.py       # OpenAI 兼容 LLM 客户端（唯一接缝）
│   │   └── platform_client.py  # Spring Boot 平台客户端
│   ├── prompts/
│   │   ├── sql.py
│   │   └── answer.py
│   └── eval/
│       ├── runner.py           # mock/real 评测
│       ├── metrics.py
│       └── cases.yaml          # 黄金用例集
└── tests/
```

## 4. State 设计

`DataAgentState`（TypedDict）：`run_id/user_id/question/route/schema_context/sql_attempts/query_result/hard_guard_result/hard_guard_feedback/execution_feedback/validation_feedback/dq_result/dq_feedback/sql_retry_count/approval_status/approval_reason/final_report/warnings/errors`。

节点之间只通过 state 传数据，禁止全局变量。

## 5. 节点设计（ChatBI）

### 5.1 ROUTER
关键词路由（complex/simple），默认 complex。

### 5.2 SCHEMA
调用 `/internal/schema/relevant` 获取 schema 上下文，不直查数据库。

### 5.3 SQL_GENERATE
调用 LLM 生成 SELECT SQL；消费 question/schemaContext/feedback（hardGuard/execution/dq）；每次生成写入 `sql_attempts`；不执行 SQL。

### 5.4 SQL_HARD_GUARD
调用 `/internal/sql/validate`。结果分三类：

| 结果 | 行为 |
|---|---|
| PASS | 进入 SQL_EXECUTE |
| retryable（SQL_EMPTY/NOT_SELECT/PARSE/SYNTAX/RULE_WARNING） | 反馈给 SQL_GENERATE 重试 |
| approval-needed（明细无 LIMIT/无时间范围/全表扫描/大扫描/熔断/敏感字段） | 进入 WAITING_APPROVAL |

### 5.5 SQL_EXECUTE
调用 `/internal/sql/execute`；Java 内部二次强制校验；审批通过后 `allowHighRisk=true` 复用同一条 SQL。

### 5.6 SQL_VALIDATE
执行结果基础合理性检查；失败反馈给 SQL_GENERATE。

### 5.7 SQL_SOFT_DQ
调用 `/internal/dq/sql-result/check` 软审核；warnings 必须带入最终回答。

### 5.8 ANSWER
调用 AnswerAgent 生成 `AnalysisReport`（summary/metrics/charts/recommendations/sql/warnings/dq）。

## 6. Human-in-the-loop

```text
SQL_HARD_GUARD 判定 approval-needed
  -> approval_status=waiting
  -> checkpoint 保存（当前进程内内存）
  -> 返回 WAITING_APPROVAL
审批 POST /api/agent/runs/{runId}/approval {"approved": true}
  -> resume_graph：复用同一条 SQL 继续执行（不重新生成，防审批对象漂移）
```

## 7. Trace 回写

每个节点经 `traced_node` 包装，回写 `POST /internal/runs/{runId}/nodes`（开始）与 `PATCH .../nodes/{nodeId}`（完成/失败），Java 侧持久化 `agent_run_node`。

## 8. 错误处理

- 失败必须转化为结构化 feedback 回流给 SQL_GENERATE。
- 重试上限 3 次；超限进入 ANSWER 返回错误报告。
- 错误分类（retryable / approval-needed / fatal）由硬校验结果驱动。

## 9. 演进方向（规划，未实现）

- **LangGraph 迁移**：用 `StateGraph` + 条件边 + `interrupt` + `SqliteSaver` 重写编排层，审批持久化跨进程可恢复。
- **语义解析 + 确定性合成**：LLM 只做语义匹配（指标/维度/过滤/时间），SQL 由合成器确定性生成；`metric_definition` 指标字典落地；长尾问题降级 raw SQL。
- **评测 harness**：golden_spec + 四层评分比较器 + FakeLLM 录制回放 + A/B 基线对比 + CI 回归门禁。
- 上述方向分别由 OpenSpec change `langgraph-migration`、`semantic-resolve-node`、`agent-eval-harness` 承接。

## 10. 验收清单

- `mvn test` 通过。
- `/api/agent/analyze`（langgraph）可返回 `AnalysisReport`。
- `/internal/sql/validate`、`/internal/sql/execute`、`/internal/dq/sql-result/check` 可独立调用。
- 高风险 SQL 不会直接执行（进入审批或拦截）。
- 所有 SQL 有审计日志。
- 测试环境不依赖真实模型/Redis/MySQL 初始化逻辑。
