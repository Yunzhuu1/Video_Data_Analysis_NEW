## Why

行业范式已转向"语义层保证质量"（NL2Metrics）：LLM 不写 SQL，只做语义匹配（指标/维度/过滤/时间），SQL 由语义层确定性合成（对标 dbt MetricFlow）。当前实现是"生成原始 SQL + 事后审计"，语义正确性（口径）恰恰是事后审计抓不住的。项目已有 `metric_def`/`metric_daily` 雏形和文档中的 `metric_definition` DDL，但未落地。

## What Changes

- 新增 `SEMANTIC_RESOLVE` 节点：输出结构化 `ResolvedIntent`（`{intent, metrics, dimensions, time_range, filters, ordering}`），LLM 只做语义匹配，不写 SQL。
- 新增 `SQL_SYNTHESIZE` 节点：按 `ResolvedIntent` 确定性合成 SQL（依据 `metric_definition.formula/source_table`），可复现、可单测。
- Java 落地 `metric_definition` 表（对齐 `docs/SpringBoot平台层设计.md` 3.4 DDL，补充 `source_table` 列）与 `MetricCatalogService`（`/internal/metrics/*`）。
- 长尾 fallback：`SEMANTIC_RESOLVE` 解析失败或覆盖不到时，降级到现有 `SQL_GENERATE` 原始生成 + 护栏 + 重试。
- 补全仓库缺失的表 DDL（`user_behavior_fact`/`content_dim`/`creator_dim`/`user_dim`/`time_dim`/`activity_dim`/`metric_definition` 收进 `schema.sql`，解决"幽灵表"）。
- `golden_spec`（见 `agent-eval-harness`）与 `ResolvedIntent` 共用同一 schema，作为节点输出契约。

## Capabilities

### New Capabilities
- `semantic-resolution`: 从自然语言解析出受控的指标查询意图（ResolvedIntent），并由确定性合成器产出 SQL；语义质量在构造期保证，长尾问题降级 raw SQL。

### Modified Capabilities
<!-- 无既有 spec 需要修改 -->

## Impact

- 代码：`agent-engine/app/graph/nodes.py`（新增 resolve/synthesize 节点）、`graph_builder.py`（图拓扑）、`app/prompts/`（语义解析 prompt）
- Java：`src/main/java/.../service/MetricCatalogService.java`（新增）、`config/DataInitializer.java`（指标种子）、`src/main/resources/schema.sql`（DDL 收编）
- 数据模型：`metric_definition` 表（替代 `metric_def`）
- API：`/internal/metrics/{code}`（新）
- 文档：架构文档、接口契约、AGENTS.md
