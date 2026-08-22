## MODIFIED Requirements

### Requirement: 指标字典落地
系统 SHALL 提供 `metric_definition` 表（含 `metric_code` 唯一键、`formula`、`dimensions`、`time_granularity`、`source_table`）与 `MetricCatalogService`，并通过 `/internal/metrics/{code}` 对外提供指标定义查询。classpath `metric_catalog.json` SHALL 作为其中列出的受管指标权威源，由独立于事实数据初始化的启动 reconciliation 校验、事务性幂等 upsert 并回读受管 projection/hash；旧数据库已有事实数据不得跳过目录同步。受管目录无法同步一致时平台 MUST fail-fast；资源未管理的数据库额外指标只告警且不得自动删除。

#### Scenario: 按代码查指标
- **WHEN** 调用 `/internal/metrics/total_plays`
- **THEN** 返回公式、可选维度、时间粒度与 `source_table`

#### Scenario: 新指标可查询
- **WHEN** 指标字典扩展至 15 个（含比率派生/跨表收益/去重计数）
- **THEN** 新指标在 metric_catalog 定义口径（formula/source_table/factFormula/factEventFilter），合成器/记忆按字典动态适配，新指标经别名表可被用户问法映射

#### Scenario: 已有事实数据的旧库幂等升级
- **WHEN** `user_behavior_fact` 已有 seed 42 数据且数据库仅含旧 7 个指标，平台以 15 指标资源目录连续启动两次
- **THEN** 第一次补齐/更新 15 个受管指标，第二次不重复插入或无条件增加 version，事实与既有聚合真值字节级不变

#### Scenario: 指标公式变更可同步
- **WHEN** 某个已存在受管 code 的资源 formula、dimensions、source/time 或 fact 表达式发生变更
- **THEN** reconciliation 更新对应权威字段并只在实际变化时递增 version，回读 projection/hash 与资源一致

## ADDED Requirements

### Requirement: 相对时间锚点运行时契约
相对时间展开 SHALL 使用最终物理查询路径对应的 source 与 time field 获取数据末日：active lineage 使用 validated plan 的 `sourceTable/timeFieldRef`，legacy 使用 `_resolve_path` 后的物理绑定。锚点 SQL SHALL 将值归一为 DATE；Python 边界 SHALL 兼容 date、datetime 与 ISO date/datetime 值并只向 `time_expand` 传规范 `YYYY-MM-DD`。

#### Scenario: datetime 锚点归一化
- **WHEN** 平台锚点结果为 `2023-10-31T23:59:59`、带 timezone 的 ISO datetime 或 JDBC DATE 的 JSON 表示
- **THEN** Agent 统一得到 `2023-10-31`，最近 7 天展开为含端点的 `2023-10-25..2023-10-31`，不产生 `Invalid isoformat` warning

#### Scenario: 锚点与物理路径同源
- **WHEN** 指标因 intent/dimensions 或 validated plan 从原始 metric source 路由到另一物理表
- **THEN** MAX 锚点和最终 SQL 时间过滤使用同一物理 source/time field，不从 metric definition 原始字段另行猜测

#### Scenario: 非法锚点受控降级
- **WHEN** 锚点为 null、无查询行或无法解析的类型/字符串
- **THEN** 记录稳定 warning 并按既有 raw/relative 降级语义继续，不伪造日期且由 R1/观测暴露

