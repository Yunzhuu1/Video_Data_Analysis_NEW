## MODIFIED Requirements

### Requirement: SQL 由确定性合成器生成
`SQL_SYNTHESIZE` 节点 SHALL 依据 `ResolvedIntent` 与 `metric_definition`（formula/source_table）确定性合成 SQL；相同 intent SHALL 生成相同 SQL；合成 SQL SHALL 引用真实表名并声明表别名，可在真实数据库上解析执行。

#### Scenario: 同意图同 SQL
- **WHEN** 两次输入相同的 `ResolvedIntent`
- **THEN** 合成器产出完全一致的 SQL 文本

#### Scenario: 合成 SQL 可复验
- **WHEN** 合成器产出 SQL
- **THEN** 该 SQL 可通过 `SQL_HARD_GUARD` 校验（或返回明确校验失败信息）

#### Scenario: 合成 SQL 引用真实表名
- **WHEN** 合成器基于 `metric_definition.sourceTable` 合成 SQL
- **THEN** FROM 子句包含真实表名与别名声明（如 `FROM metric_daily md`），且该 SQL 可在真实 MySQL 上解析执行，不得出现未声明别名的 `FROM md`
