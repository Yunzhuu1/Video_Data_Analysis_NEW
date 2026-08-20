## MODIFIED Requirements

### Requirement: 数据模型 DDL 可复现
所有 mock 表（`user_behavior_fact`/`content_dim`/`creator_dim`/`user_dim`/`time_dim`/`activity_dim`/`metric_definition`/`metric_daily` 等）的建表语句 SHALL 收编进 `src/main/resources/schema.sql`，`DataInitializer` 仅负责种子数据。

#### Scenario: 数据模型规模化
- **WHEN** 数据模型扩展（新增 `creator_revenue`/`video_revenue`/`user_retention`/`content_quality` 表、指标 7→15）
- **THEN** 新表 DDL 入 schema.sql、DataInitializer 以 seed 42 确定性灌入含真实业务模式（长尾/稀疏/异常）的数据、TableSchemaRegistry 注册新表（表类型 FACT/DIM），门禁 AST 校验可识别

### Requirement: 指标字典落地
系统 SHALL 提供 `metric_definition` 表（含 `metric_code` 唯一键、`formula`、`dimensions`、`time_granularity`、`source_table`）与 `MetricCatalogService`，并通过 `/internal/metrics/{code}` 对外提供指标定义查询。

#### Scenario: 新指标可查询
- **WHEN** 指标字典扩展至 15 个（含比率派生/跨表收益/去重计数）
- **THEN** 新指标在 metric_catalog 定义口径（formula/source_table/factFormula/factEventFilter），合成器/记忆按字典动态适配，新指标经别名表可被用户问法映射
