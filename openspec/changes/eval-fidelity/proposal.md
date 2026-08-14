## Why

sql-gate-unification 落地后真实评测端到端 73.91%（17/23）。拆解 6 个失败：3 个（c04/c06/c10）是"事实表重查询被门禁正确拦截走审批，但评测按'没跑完'判失败"（评测语义问题）；1 个（c18）是"意图=明细全量但 LLM 生成的 SQL 恰好合规绕过了拦截"（意图层风险未参与，覆盖缺口）；2 个（c11/c17）是"回答质量"（LLM 报告缺 metrics/DQ 关键词）。**没有一个是门禁误伤**，但评测定义与意图层覆盖让数字低估了系统真实能力。

## What Changes

- **评测语义修正**：审批暂停用例的判定——risk 类型用例（期望 `WAITING_APPROVAL`）拦截即 PASS（对齐 c22/c19）；其余类型若被门禁拦截，runner 自动调用审批接口放行并继续验证审批后完整链路（产出报告、字段检查），让 c04/c06/c10 如实通过。
- **意图层风险**：`SEMANTIC_RESOLVE` 已知 `intent=detail` 且意图无时间范围时，把意图信号传入门禁（`/internal/sql/validate` 请求增加 intent 字段），静态层结合 intent 判定：**`intent=detail` 且 `intent.time_range` 缺失 → 无条件 `APPROVAL_NEEDED`**（与 LLM 生成的 SQL 形态无关，解决 c18 确定性拦截）；聚合意图豁免 LIMIT 规则（修 c04/c10 误伤）。
- **回答质量兜底**：`AnswerAgent` 在 LLM 回答缺 metrics 时用查询结果兜底生成基本指标；回答必须带 DQ 警告（修 c11/c17）。
- **意图-形态一致性**（收紧）：`intent ∈ {aggregate,trend,ranking}` 但 SQL 无 GROUP BY/聚合函数且触碰 FACT → `RETRYABLE`（LLM 形态写错，重写）。
- **评测保真度自证**：报告增加 `auto_released` 计数/比例（非风险用例被拦截后自动放行的比例），解耦"端到端上升"与"门禁不过度拦截"。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-eval`: 新增「审批暂停用例的评测语义」——拦截即 PASS / 自动放行补跑；回答质量断言（metrics/DQ 提示必填）。
- `semantic-resolution`: 新增「意图层风险信号」——`ResolvedIntent.intent` 透传门禁，`intent=detail` 且无时间范围时确定性审批（ranking 无时间范围由既有 SQL 级时间范围规则覆盖，不新增 intent 信号）。
- `chatbi-mainline`: 门禁请求携带 intent 入参；聚合查询豁免 LIMIT 规则（`DETAIL_QUERY_WITHOUT_LIMIT` 仅适用非聚合）。

## Impact

- **Python**：`app/agents/answer_agent.py`（回答兜底）、`app/graph/nodes.py`（intent 信号透传）、`app/clients/platform_client.py`（validate_sql 带 intent）、`app/eval/runner.py`（审批自动放行）、`app/eval/cases.yaml`（c04/c06/c10/c18 期望）。
- **Java**：`SqlStaticAnalyzer`（intent 入参、聚合豁免 LIMIT、detail 强制）、`SqlGateService`/DTO（intent 字段）。
- **评测**：`docs/eval-report.md`（重跑快照）、`docs/开发日志.md`。
- **验证**：Python pytest + ruff、Java `mvn test`、真实评测重跑。
- **非目标**：dimensions 抽取优化（L4 61.54%）、门禁规则本身（已收敛）、记忆系统。

