## MODIFIED Requirements

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent` 与 `metric_definition`（formula/source_table）确定性合成 SQL；相同 intent SHALL 生成相同 SQL；合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。合成器 SHALL 支持**同源表多指标聚合**（多个指标经 `_resolve_path` 后全部落在 `metric_daily` 列路径时，单 FROM + 多 SELECT 表达式列，共享 group-by/time/filter）；非 metric_daily 路径多指标（跨源或事实路径）与多指标 ranking/detail SHALL 明确降级（SynthesisError → raw SQL）。`time_range.type == "relative"` 时，合成前 SHALL 以**数据末日为锚**展开为 absolute 区间（含端点），合成 SQL 含时间过滤。合成器 SHALL 支持**指标值过滤**（filters[].field 为指标 code 时生成 HAVING）与**同粒度冲突多指标**（指标组合存在来源冲突或 eventFilter 冲突且共享维度键时，子查询 JOIN）。

#### Scenario: 指标值过滤（HAVING）
- **WHEN** ResolvedIntent.filters 含指标 code 字段（如 completion_rate）且 op ∈ {>, >=, <, <=}
- **THEN** 合成 SQL 生成 HAVING 条件（聚合表达式 + op + value）；维度字段过滤仍走 WHERE

#### Scenario: 冲突多指标（子查询 JOIN）
- **WHEN** 多指标存在来源冲突（不同 sourceTable，如 play_detail + user_behavior_fact）或 eventFilter 冲突（同源 fact 不同 filter，如 play vs like）且共享同一组维度键/时间/过滤
- **THEN** 合成子查询 JOIN SQL（各指标独立聚合子查询 + 各自 eventFilter，按维度键对齐），在真实数据库可解析执行

#### Scenario: 异粒度跨源降级
- **WHEN** 跨源多指标无法按同一组维度键聚合（粒度不对齐）
- **THEN** 抛 SynthesisError 降级（不产出错误 JOIN）
