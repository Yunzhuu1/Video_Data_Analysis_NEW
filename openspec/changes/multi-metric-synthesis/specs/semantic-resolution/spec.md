## MODIFIED Requirements

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent` 与 `metric_definition`（formula/source_table）确定性合成 SQL；相同 intent SHALL 生成相同 SQL；合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。合成器 SHALL 支持**同源表多指标聚合**（多个指标来自同一 source_table 时，单 FROM + 多 SELECT 表达式列，共享 group-by/time/filter）；跨源表多指标与多指标 ranking/detail SHALL 明确降级（SynthesisError → raw SQL）。

#### Scenario: 同源表多指标聚合
- **WHEN** ResolvedIntent 的 metrics 全部来自同一 source_table（如 metric_daily 的 total_plays + total_likes），且 intent ∈ {aggregate, trend}、共享同 group-by 集
- **THEN** 合成单 FROM 多 SELECT 列 SQL（每列 `agg_expr AS code`），在真实数据库可解析执行

#### Scenario: 跨源表多指标降级
- **WHEN** metrics 来自不同 source_table（如 play_detail + user_behavior_fact）
- **THEN** 抛 SynthesisError，节点降级 raw SQL 生成（sql_source=fallback），不产出错误 SQL

#### Scenario: 约束显式失败
- **WHEN** 多指标但 intent 为 ranking/detail，或维度/时间/过滤/排序不一致
- **THEN** 抛 SynthesisError（显式失败优于产出错误 SQL）
