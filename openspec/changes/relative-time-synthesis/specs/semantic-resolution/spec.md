## MODIFIED Requirements

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent` 与 `metric_definition`（formula/source_table）确定性合成 SQL；相同 intent SHALL 生成相同 SQL；合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。合成器 SHALL 支持**同源表多指标聚合**（多个指标经 `_resolve_path` 后全部落在 `metric_daily` 列路径时，单 FROM + 多 SELECT 表达式列，共享 group-by/time/filter）；非 metric_daily 路径多指标（跨源或事实路径）与多指标 ranking/detail SHALL 明确降级（SynthesisError → raw SQL）。`time_range.type == "relative"` 时，合成前 SHALL 以**数据末日为锚**展开为 absolute 区间（含端点），合成 SQL 含时间过滤。

#### Scenario: 相对时间展开
- **WHEN** ResolvedIntent 的 time_range 为 relative（如 {amount: 7, unit: "day"}）
- **THEN** 合成前展开为 absolute 区间（锚点=数据末日，含端点：最近7天 = 末日往前 6 天），合成 SQL 含 `WHERE <timeField> BETWEEN start AND end`

#### Scenario: 锚点查询失败降级
- **WHEN** 数据末日锚点查询失败（网络/权限）
- **THEN** 保持 relative（合成器现状），记录 warning 且不打断主链路；R1 侧以 value_mismatch 暴露（不静默）
