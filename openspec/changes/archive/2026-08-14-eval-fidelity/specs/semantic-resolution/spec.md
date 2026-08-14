## ADDED Requirements

### Requirement: 意图层风险信号
`SEMANTIC_RESOLVE` SHALL 把 `ResolvedIntent` 的 `intent` 透传给 SQL 门禁，使拦截可结合意图判定，不依赖 LLM 生成 SQL 的形态。

#### Scenario: detail 且意图无时间范围强制审批
- **WHEN** `ResolvedIntent.intent=detail` 且 `intent.time_range` 缺失或 `type == "none"`
- **THEN** 门禁返回 `APPROVAL_NEEDED`（与 LLM 生成的 SQL 形态无关；注意 time_range 有 `{"type":"none"}` 默认值，type=none 即视为无时间范围）

#### Scenario: detail 且意图带时间范围
- **WHEN** `ResolvedIntent.intent=detail` 且 `intent.time_range` 存在
- **THEN** 门禁按 SQL 检查（LIMIT + 时间范围），不无条件拦截

#### Scenario: 聚合意图豁免 LIMIT
- **WHEN** `ResolvedIntent.intent ∈ {aggregate, trend, ranking}` 或 SQL 含 GROUP BY/聚合函数
- **THEN** `DETAIL_QUERY_WITHOUT_LIMIT` 不适用（聚合不返回明细行）；时间范围规则仍生效

#### Scenario: 意图-形态一致性
- **WHEN** `intent ∈ {aggregate,trend,ranking}` 但 SQL 无 GROUP BY/聚合函数且触碰 FACT 表
- **THEN** 门禁返回 `RETRYABLE`（LLM 形态写错，重写）
