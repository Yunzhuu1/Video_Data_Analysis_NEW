# Agent 拓扑说明

本文档描述当前项目正在落地的 ChatBI Agent 主链路。历史的大而全 Multi-Agent 方案已经收敛为以 Text2SQL 为核心的可执行链路，RAG、归因和 DBQA 暂作为后续扩展。

## 分层职责

| 层级 | 负责人 | 职责 |
|---|---|---|
| 对外服务层 | Spring Boot | 接收用户请求、选择引擎、返回 `AnalysisReport` |
| 平台工具层 | Spring Boot | SQL 校验、SQL 执行、DQ 审核、指标查询、运行记录、审批恢复 |
| Agent 编排层 | Python Agent Engine | 状态图编排、节点跳转、SQL 生成重试、等待审批、最终回答 |
| 模型能力层 | LLM Client | SQL 生成、回答生成、必要的轻量判断 |

## 当前 ChatBI 主图

```text
ROUTER
  -> SCHEMA
  -> SQL_GENERATE
  -> SQL_HARD_GUARD
  -> SQL_EXECUTE
  -> SQL_VALIDATE
  -> SQL_SOFT_DQ
  -> ANSWER
```

`/analyze` 仅支持 `graphMode=chatbi`。历史全量图（RAG/归因/DBQA）已下线，不再保留兼容。

## 节点说明

### ROUTER

判断请求是否进入 ChatBI 主链路。当前阶段可以默认进入 ChatBI，后续再扩展闲聊、归因分析、报表解释等分支。

输入：

```text
question
```

输出：

```text
route = chatbi
```

### SCHEMA

获取或构造当前问题需要的 Schema 上下文，减少 SQL 生成的搜索空间。

当前实现允许使用平台层 Schema 接口或本地 mock schema。真实联调时应优先通过 Spring Boot 获取平台侧 Schema。

### SQL_GENERATE

调用 SQLGenerationAgent 生成 MySQL SELECT SQL。

输入：

```text
question
schemaContext
previousFeedback?
```

输出：

```text
sql
```

要求：

- 只生成 SELECT。
- 不臆测不存在的表和字段。
- 收到硬校验或执行错误反馈后，必须基于反馈重写 SQL。
- 超过重试次数后终止并返回错误报告。

### SQL_HARD_GUARD

调用 Spring Boot 平台层 `/internal/sql/validate` 做硬校验。

校验结果分三类：

| 类型 | 行为 |
|---|---|
| PASS | 进入 SQL_EXECUTE |
| retryable | 把失败原因反馈给 SQL_GENERATE 重试 |
| approval-needed | 进入 `WAITING_APPROVAL`，等待人工审批 |

典型 retryable 问题：

- `SQL_EMPTY`
- `SQL_NOT_SELECT`
- `SQL_PARSE_ERROR`
- `SQL_SYNTAX_ERROR`
- `SQL_RULE_WARNING`

典型 approval-needed 问题：

- `DETAIL_QUERY_WITHOUT_LIMIT`
- `DETAIL_QUERY_WITHOUT_TIME_RANGE`
- `SQL_FULL_SCAN`
- `SQL_LARGE_SCAN`
- `SQL_CIRCUIT_BREAKER`
- `SENSITIVE_FIELD_ACCESS`

### SQL_EXECUTE

调用 Spring Boot SQL Gateway 执行 SQL。

要求：

- Python 不直接连接数据库。
- SQL 执行必须经过 Spring Boot 的统一安全入口。
- 执行失败时错误信息回流到 SQL_GENERATE，触发重试。

### SQL_VALIDATE

对 SQL 执行后的结果做基础合理性检查。当前可作为轻量节点保留，后续可并入更完整的 Execution Guidance。

### SQL_SOFT_DQ

调用 Spring Boot `/internal/dq/sql-result/check` 做软审核。

软审核不直接阻断主链路，但必须把 warnings 和 DQ 结果带入最终回答，避免模型忽略数据质量风险。

### ANSWER

调用 AnswerAgent 生成结构化 `AnalysisReport`。

输出字段需要兼容 Spring Boot DTO：

```text
summary
metrics
charts
recommendations
sql
warnings
dq
```

## Human-in-the-loop

当 SQL_HARD_GUARD 判定需要审批时，Agent Engine 返回等待状态：

```text
status = WAITING_APPROVAL
runId
sql
approvalReasons
```

Spring Boot 审批接口：

```http
POST /api/agent/runs/{runId}/approval
Content-Type: application/json

{"approved": true}
```

审批通过后，Agent Engine 使用同一条 SQL 继续执行，并设置 `allowHighRisk=true`，避免重新生成 SQL 导致审批对象漂移。

## 演进方向（规划，未实现）

以下能力属于规划方向，不作为当前 ChatBI 主链路的完成标准：

- **LangGraph 迁移（已完成）**：编排层已基于 LangGraph StateGraph（条件边 + interrupt + SQLite checkpoint）重写，审批持久化跨进程可恢复。
- **语义解析 + 确定性合成**：LLM 只做语义匹配（指标/维度/过滤/时间），SQL 由合成器确定性生成；`metric_definition` 指标字典落地；长尾问题降级 raw SQL。
- **评测 harness**：golden_spec + 四层评分比较器 + FakeLLM 录制回放 + A/B 基线对比 + CI 回归门禁。

剩余方向由 OpenSpec change `semantic-resolve-node`、`agent-eval-harness` 承接，不重新打乱当前 ChatBI 主链路。
