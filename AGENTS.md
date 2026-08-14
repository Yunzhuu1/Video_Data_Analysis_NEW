# Agent 拓扑说明

本文档描述当前项目正在落地的 ChatBI Agent 主链路。历史的大而全 Multi-Agent 方案已经收敛为以 Text2SQL 为核心的可执行链路，RAG、归因和 DBQA 暂作为后续扩展。

## 开发与测试日志（强制规范）

每次进行开发、Bug 修复或测试后，**必须**在 `docs/开发日志.md` 追加日志条目（倒序，最新在最上），并保持与既有条目格式一致。

条目必须包含：

- 日期 + 一句话标题
- 做了什么（开发 / 测试内容）
- Bug（如有）：现象 → 原因 → 修复（编号 BUG-xxx）
- 测试过程与结果：命令、通过/失败数、关键指标
- 待办 / 下一步

格式模板见 `docs/开发日志.md` 顶部。

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
  -> SEMANTIC_RESOLVE      # LLM 只做语义匹配，输出 ResolvedIntent
  -> SQL_SYNTHESIZE        # 确定性合成 SQL
  -> SQL_HARD_GUARD
  -> SQL_EXECUTE
  -> SQL_SOFT_DQ
  -> ANSWER

SEMANTIC_RESOLVE 失败/低置信 或 SQL_SYNTHESIZE 失败
  -> SQL_GENERATE（raw LLM SQL 降级，source=fallback）
  -> SQL_HARD_GUARD ...
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

调用 Spring Boot 平台层 `/internal/sql/validate`（统一门禁 `SqlGateService`，唯一权威）做硬校验。

门禁返回三态裁决 `verdict`：

| 裁决 | 行为 |
|---|---|
| `PASS` | 进入 SQL_EXECUTE |
| `RETRYABLE` | 把 `code/reason/suggestion` 反馈给 SQL_GENERATE 重试 |
| `APPROVAL_NEEDED` | 进入 `WAITING_APPROVAL`，等待人工审批 |

门禁内部两阶段：**静态语义层**（jsqlparser AST，基于语义层模型：schema.sql 解析的表-列注册表/表类型/敏感列，不依赖业务库）→ **计划层**（EXPLAIN，表类型感知：FACT 全扫/大扫描 → 审批，AGGREGATE/DIM 全扫 → 放行，TEMP_TABLE/FILESORT 且 FACT → 可重试）。

典型 `RETRYABLE` 问题：

- `SQL_EMPTY` / `SQL_NOT_SELECT` / `SQL_PARSE_ERROR`
- `SQL_UNKNOWN_TABLE` / `SQL_UNKNOWN_COLUMN`
- `SQL_RULE_WARNING` / `SQL_TEMP_TABLE` / `SQL_FILESORT`（FACT 表）

典型 `APPROVAL_NEEDED` 问题：

- `DETAIL_QUERY_WITHOUT_LIMIT` / `DETAIL_QUERY_WITHOUT_TIME_RANGE`
- `SQL_FULL_SCAN` / `SQL_LARGE_SCAN`（FACT 表）
- `SENSITIVE_FIELD_ACCESS`（含 `SELECT *` 命中敏感列，如 `user_id`）

### SQL_EXECUTE

调用 Spring Boot SQL Gateway 执行 SQL。

要求：

- Python 不直接连接数据库。
- SQL 执行必须经过 Spring Boot 的统一安全入口。
- 执行失败时错误信息回流到 SQL_GENERATE，触发重试。

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

审批通过后，Agent Engine 使用同一条 SQL 继续执行（`allowHighRisk=true`），避免重新生成 SQL 导致审批对象漂移。

**审批放行不变式**：门禁只在 `SQL_HARD_GUARD` 调用一次；`SQL_EXECUTE` 永不重跑门禁（execute 只执行+熔断），因此已审批的 SQL 不会被二次拦截。

## 演进方向（规划，未实现）

以下能力属于规划方向，不作为当前 ChatBI 主链路的完成标准：

- **LangGraph 迁移（已完成）**：编排层已基于 LangGraph StateGraph（条件边 + interrupt + SQLite checkpoint）重写，审批持久化跨进程可恢复。
- **语义解析 + 确定性合成**：LLM 只做语义匹配（指标/维度/过滤/时间），SQL 由合成器确定性生成；`metric_definition` 指标字典落地；长尾问题降级 raw SQL。
- **评测 harness（已完成）**：golden_spec + 四层评分比较器 + FakeLLM 录制回放 + A/B 对比 + mock/replay/real 模式。

当前 ChatBI 主链路已完整落地（语义解析/合成/护栏/HITL/评测），不再有规划中的主线改动。
