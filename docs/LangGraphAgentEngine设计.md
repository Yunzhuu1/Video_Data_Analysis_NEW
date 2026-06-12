# LangGraph Agent Engine 设计

## 1. 定位

LangGraph Agent Engine 是 DataAgent 的状态机编排层。

它负责：

- Agent 节点编排。
- 条件分支。
- 循环修正。
- 并行扇出。
- Human-in-the-loop。
- Checkpoint 与恢复。
- 节点级 Trace 回写。

它不负责：

- 直接执行 SQL。
- 判断用户是否有权限。
- 持久化业务数据。
- 维护指标字典。
- 做生产审计。

这些能力由 Spring Boot 平台层提供。

## 2. 服务结构

```text
agent-engine/
├── pyproject.toml
├── app/
│   ├── main.py
│   ├── settings.py
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── graph/
│   │   ├── state.py
│   │   ├── graph_builder.py
│   │   ├── nodes.py
│   │   ├── edges.py
│   │   └── checkpoints.py
│   ├── agents/
│   │   ├── router_agent.py
│   │   ├── schema_agent.py
│   │   ├── sql_agent.py
│   │   ├── validation_agent.py
│   │   ├── rag_agent.py
│   │   ├── insight_agent.py
│   │   ├── recommendation_agent.py
│   │   ├── dbqa_agent.py
│   │   └── human_approval_agent.py
│   ├── clients/
│   │   ├── platform_client.py
│   │   ├── llm_client.py
│   │   └── vector_client.py
│   ├── prompts/
│   │   ├── router.py
│   │   ├── schema.py
│   │   ├── sql.py
│   │   ├── rag.py
│   │   ├── insight.py
│   │   └── dbqa.py
│   ├── eval/
│   │   ├── cases.yaml
│   │   ├── runner.py
│   │   └── metrics.py
│   └── observability/
│       ├── trace.py
│       └── events.py
└── tests/
    ├── test_graph_flow.py
    ├── test_sql_retry.py
    ├── test_rag.py
    └── test_eval_metrics.py
```

## 3. State 设计

所有节点通过 `DataAgentState` 传递状态。禁止节点之间通过全局变量传递数据。

```python
from typing import Literal, TypedDict

class SqlAttempt(TypedDict):
    sql: str
    success: bool
    result_preview: str | None
    error: str | None
    warnings: list[str]
    risk_level: str | None

class RagResult(TypedDict):
    themes: list[str]
    negative_ratio: float
    representative_comments: list[str]
    summary: str
    confidence: float

class DataAgentState(TypedDict, total=False):
    run_id: str
    user_id: str
    question: str

    route: Literal["simple", "complex"]
    schema_context: str

    sql_attempts: list[SqlAttempt]
    query_result: dict
    validation_feedback: str
    sql_retry_count: int

    rag_result: RagResult
    cross_validation: str

    insight_report: dict
    recommendations: list[str]

    dbqa_status: Literal["pass", "fail"]
    dbqa_feedback: str
    supplemental_query_result: dict

    approval_status: Literal["not_required", "waiting", "approved", "rejected"]
    approval_reason: str

    final_report: dict
    errors: list[str]
```

## 4. Agent 图

目标图：

```text
START
  |
  v
RouterNode
  | simple
  v
SimpleSQLNode -> FinalReportNode -> END

RouterNode
  | complex
  v
SchemaNode
  |
  v
SQLGenerateNode
  |
  v
SQLExecuteNode
  |
  v
SQLValidateNode
  | invalid/error and retry_count < 3
  +---------------------> SQLGenerateNode
  |
  | high_risk
  v
HumanApprovalNode
  | approved
  v
SQLExecuteNode
  | rejected
  v
FailNode

SQLValidateNode
  | pass
  v
RAGNode
  |
  v
CrossValidationNode
  |
  +--------------------+
  |                    |
  v                    v
InsightNode       RecommendationNode
  |                    |
  +---------+----------+
            v
        MergeNode
            |
            v
        DBQANode
            | missing_data
            v
        SupplementalSQLNode
            |
            v
        InsightNode

DBQANode
  | pass
  v
FinalReportNode
  |
  v
END
```

## 5. 节点设计

### 5.1 RouterNode

职责：

- 判断问题走 simple 还是 complex。
- 优先关键词短路。
- 模糊场景调用 cheap model。

输入：

```text
question
```

输出：

```text
route
```

规则：

- `有哪些/列出/展示` 且不包含趋势、对比、原因，走 simple。
- `为什么/原因/对比/趋势/归因/环比/同比` 走 complex。

### 5.2 SchemaNode

职责：

- 调用 Spring Boot `/internal/schema/relevant`。
- 获取裁剪后的 Schema。

不直接查询 INFORMATION_SCHEMA。

### 5.3 SQLGenerateNode

职责：

- 根据问题、schema、指标定义和上一轮错误生成 SQL。
- 只生成 SELECT。
- 如果涉及指标，先调用平台层指标接口。

输出：

```text
sql_attempts[-1].sql
```

要求：

- SQL 生成节点不执行 SQL。
- 不把 SQL 执行错误吞掉。
- 每次 retry 必须保留历史 attempt。

### 5.4 SQLExecuteNode

职责：

- 调用 Spring Boot `/internal/sql/execute`。
- 接收结构化 `SqlExecuteResult`。

如果平台层返回 `riskLevel=HIGH` 且 `success=false`，进入 HumanApprovalNode。

### 5.5 SQLValidateNode

职责：

- 判断 SQL 结果是否足以回答问题。
- 判断是否需要补充查询。
- 判断是否重试。

判断来源：

- SQL 执行成功与否。
- 平台规则 warnings。
- 查询结果是否为空。
- LLM semantic validation。

输出：

```text
validation_feedback
```

### 5.6 RAGNode

职责：

- 将指标问题改写成评论检索关键词。
- 检索评论证据。
- 提取主题、负面占比、代表评论。
- 产出 confidence。

第一版可以调用 Spring Boot 现有 RAG 能力。后续再迁移到 Python。

### 5.7 CrossValidationNode

职责：

- 根据 RAG 主题查询结构化播放明细。
- 验证评论指控是否被数据支持。

规则：

- `confidence < 0.3` 时跳过。
- 广告/卡顿主题优先验证跳出时间分布。
- 活动/内容主题优先验证活动前后指标变化。

### 5.8 InsightNode

职责：

- 生成结构化分析报告。
- 融合 SQL 数据、RAG 证据、交叉验证。
- 不输出运营建议。

输出：

```json
{
  "summary": "...",
  "period": "...",
  "metrics": [],
  "charts": []
}
```

### 5.9 RecommendationNode

职责：

- 生成 1-3 条运营建议。
- 建议必须基于数据或评论证据。

输出：

```json
["建议1", "建议2"]
```

### 5.10 DBQANode

职责：

- 检查报告是否完整回答问题。
- 判断是否缺少维度。
- 必要时触发补充查询。

输出：

```text
dbqa_status
dbqa_feedback
```

### 5.11 HumanApprovalNode

职责：

- 对高风险 SQL 暂停执行。
- 等待用户审批。
- 审批通过后从 checkpoint 恢复。

触发条件：

- 明细表查询。
- 敏感字段查询。
- EXPLAIN rows 超阈值。
- 无时间范围的大表查询。

## 6. Trace 回写

每个节点必须通过 `PlatformClient` 回写状态。

```python
async def traced_node(state: DataAgentState, node_name: str, fn):
    node_id = await platform.start_node(
        run_id=state["run_id"],
        node_name=node_name,
        input_payload=state
    )
    try:
        new_state = await fn(state)
        await platform.finish_node(node_id=node_id, output_payload=new_state)
        return new_state
    except Exception as exc:
        await platform.fail_node(node_id=node_id, error=str(exc))
        raise
```

注意：

- 输入输出 payload 要做截断。
- 不记录 API Key、数据库密码、完整用户隐私数据。
- 失败必须保留异常类型和消息。

## 7. Checkpoint 策略

第一版：

- 使用内存 checkpoint，仅支持单进程演示。

第二版：

- 使用 SQLite/Postgres checkpoint。

第三版：

- 和 Spring Boot 的 `agent_run_node` 结合，实现跨服务恢复。

Human-in-the-loop 必须依赖持久化 checkpoint，否则服务重启后无法恢复。

## 8. 错误处理

错误分类：

| 类型 | 处理 |
|---|---|
| LLM 调用失败 | 重试 1 次，失败进入 fallback |
| SQL 编译失败 | 带错误反馈回 SQLGenerateNode |
| SQL 高风险 | 进入 HumanApprovalNode |
| RAG 无结果 | 返回空 RAG，confidence=0 |
| Insight 失败 | fallbackReport |
| Recommendation 失败 | 返回空列表 |
| DBQA 失败 | 放行当前报告但记录 warning |

## 9. 测试要求

必须覆盖：

- Router 条件分支。
- SQL retry 循环。
- 高风险 SQL 进入审批。
- RAG confidence 低时跳过交叉验证。
- DBQA 缺失数据时触发补充查询。
- 节点失败时回写 Run Trace。

## 10. 验收清单

- `/analyze` 能执行完整图。
- 所有节点状态可在 Spring Boot 查询。
- SQL 错误能触发自动修正。
- 高风险 SQL 能暂停等待审批。
- RAG confidence 能影响路径。
- DBQA 能触发补充查询。
- 评测 runner 能批量执行 cases。
