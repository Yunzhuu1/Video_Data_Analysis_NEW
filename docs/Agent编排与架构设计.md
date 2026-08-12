# Agent 编排与架构设计

> 本文档描述当前真实实现的结构与演进方向。由 `DataAgent总体架构与迁移路线.md` 与 `LangGraphAgentEngine设计.md` 合并重写而来，只保留与实现一致的内容。

## 1. 定位

双服务架构：

- **Spring Boot 平台层**：对外 API、SQL 校验/执行/DQ、审计、Run Trace、审批入口、Schema 缓存、Token 统计。只做确定性平台治理，不做编排。
- **Python Agent Engine**：ChatBI 状态图编排（基于 LangGraph `StateGraph`：显式节点/条件边/`interrupt` + SQLite 持久化 checkpoint）、SQL 生成、失败重试、高风险 SQL 等待审批、最终回答生成。

边界原则：

- Python 不直连数据库；所有 SQL 必须过 Spring Boot 统一入口。
- Java 负责"能不能查、怎么安全查、怎么审计"；Python 负责"怎么编排、下一步走哪"。
- 确定性平台能力下沉 Java；LLM 只做生成与轻量判断。

## 2. 当前主链路（ChatBI）

```text
User -> Spring Boot /api/agent/analyze -> LangGraphClient -> Python /analyze
  -> ROUTER -> SCHEMA -> SEMANTIC_RESOLVE -> SQL_SYNTHESIZE -> SQL_HARD_GUARD
  -> SQL_EXECUTE -> SQL_VALIDATE -> SQL_SOFT_DQ -> ANSWER
  -> AnalysisReport

  SEMANTIC_RESOLVE 失败/低置信/合成失败
    -> SQL_GENERATE（raw LLM SQL 降级，source=fallback）-> SQL_HARD_GUARD ...
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
│   │   ├── graph_builder.py    # LangGraph StateGraph + 条件边 + facades
│   │   ├── nodes.py            # chatbi 8 节点
│   │   └── checkpoints.py      # SQLite checkpointer（AsyncSqliteSaver）
│   ├── agents/
│   │   ├── sql_agent.py        # SQL 生成 Agent（fallback）
│   │   ├── semantic_resolver.py# 语义解析 Agent（NL -> ResolvedIntent）
│   │   └── answer_agent.py     # 回答生成 Agent
│   ├── synthesis/
│   │   └── sql_synthesizer.py  # 确定性 SQL 合成器
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

### 5.3 SEMANTIC_RESOLVE
调用 LLM 做**语义匹配**（不写 SQL）：基于指标字典把问题解析为结构化 `ResolvedIntent`（intent/metrics/dimensions/time_range/filters/ordering + confidence/coverage）。低置信或无候选时 `semantic_ok=false`。

### 5.4 SQL_SYNTHESIZE
按 `ResolvedIntent` + `metric_definition`（formula/source_table/fact_formula）**确定性合成** SQL（同意图同 SQL）；metric_daily 按分组粒度决定是否 SUM；ranking/内容级走明细事实表。合成失败（如多指标）降级 `SQL_GENERATE`。

### 5.5 SQL_GENERATE（fallback）
语义路径覆盖不到时，调用 LLM 生成原始 SELECT SQL；消费 feedback（hardGuard/execution/dq）；结果标记 `source=fallback`。

### 5.6 SQL_HARD_GUARD
调用 `/internal/sql/validate`。结果分三类：

| 结果 | 行为 |
|---|---|
| PASS | 进入 SQL_EXECUTE |
| retryable（SQL_EMPTY/NOT_SELECT/PARSE/SYNTAX/RULE_WARNING） | 反馈给 SQL_GENERATE 重试 |
| approval-needed（明细无 LIMIT/无时间范围/全表扫描/大扫描/熔断/敏感字段） | 进入 WAITING_APPROVAL |

### 5.7 SQL_EXECUTE
调用 `/internal/sql/execute`；Java 内部二次强制校验；审批通过后 `allowHighRisk=true` 复用同一条 SQL。

### 5.8 SQL_VALIDATE
执行结果基础合理性检查；失败反馈给 SQL_GENERATE。

### 5.9 SQL_SOFT_DQ
调用 `/internal/dq/sql-result/check` 软审核；warnings 必须带入最终回答。

### 5.10 ANSWER
调用 AnswerAgent 生成 `AnalysisReport`（summary/metrics/charts/recommendations/sql/warnings/dq）。

## 6. Human-in-the-loop

```text
SQL_HARD_GUARD 判定 approval-needed
  -> 条件边进入 APPROVAL 节点，interrupt() 挂起
  -> 状态由 SQLite checkpointer 持久化（跨进程/重启可恢复）
  -> 返回 WAITING_APPROVAL
审批 POST /api/agent/runs/{runId}/approval {"approved": true}
  -> resume：Command(resume=True) 从 APPROVAL 继续
  -> 复用同一条 SQL 执行（不重新生成，防审批对象漂移）
```

## 7. Trace 回写

每个节点经 `traced_node` 包装，回写 `POST /internal/runs/{runId}/nodes`（开始）与 `PATCH .../nodes/{nodeId}`（完成/失败），Java 侧持久化 `agent_run_node`。

## 8. 错误处理

- 失败必须转化为结构化 feedback 回流给 SQL_GENERATE。
- 重试上限 3 次；超限进入 ANSWER 返回错误报告。
- 错误分类（retryable / approval-needed / fatal）由硬校验结果驱动。

## 9. 演进方向

- **LangGraph 迁移（已完成）**：编排层已基于 `StateGraph` + 条件边 + `interrupt` + SQLite checkpoint 重写，审批持久化跨进程可恢复。
- **语义解析 + 确定性合成（已完成）**：`SEMANTIC_RESOLVE`（NL -> `ResolvedIntent`）+ `SQL_SYNTHESIZE`（确定性合成）已接入主链路；`metric_definition` 指标字典与 `MetricCatalogService` 落地；长尾问题降级 raw SQL。
- **评测 harness（规划）**：golden_spec + 四层评分比较器 + FakeLLM 录制回放 + A/B 基线对比 + CI 回归门禁（OpenSpec change `agent-eval-harness`）。

## 10. 验收清单

- `mvn test` 通过。
- `/api/agent/analyze`（langgraph）可返回 `AnalysisReport`。
- `/internal/sql/validate`、`/internal/sql/execute`、`/internal/dq/sql-result/check` 可独立调用。
- 高风险 SQL 不会直接执行（进入审批或拦截）。
- 所有 SQL 有审计日志。
- 测试环境不依赖真实模型/Redis/MySQL 初始化逻辑。
