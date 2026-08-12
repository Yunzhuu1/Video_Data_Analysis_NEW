## Context

当前链路：`SCHEMA → SQL_GENERATE(LLM 写 SQL) → SQL_HARD_GUARD → ...`。新方向：`SEMANTIC_RESOLVE(LLM 只解析) → SQL_SYNTHESIZE(确定性合成) → SQL_HARD_GUARD → ...`。`legacy-cleanup` 已删除 RAG/DBQA 分支；`langgraph-migration` 提供真 LangGraph 编排底座。本项目已存在 `metric_def(metric_name, formula, dimension, time_granularity)`、`metric_daily(date, category, total_plays, ...)` 与文档 `metric_definition` DDL。

## Goals / Non-Goals

**Goals:**
- LLM 不再直接写 SQL；产出结构化 `ResolvedIntent`。
- SQL 由确定性合成器生成（给定同一 intent 永远同一条 SQL）。
- 指标字典落地（`metric_definition` + `MetricCatalogService`），支撑解析与合成。
- 覆盖不到的开放问题可降级到 raw SQL 生成（保留护栏）。

**Non-Goals:**
- 不做完整 MetricFlow 级指标编译/版本化（留给后续；本版支持公式模板 + source_table 即可）。
- 不实现 clarifyAgent 消歧交互（实习已覆盖；本版仅支持"解析失败降级"与"多候选时按规则优先"）。
- 不建设评测（由 `agent-eval-harness` 承接；但 `ResolvedIntent` schema 与其 `golden_spec` 共用）。

## Decisions

- **决策 1：`ResolvedIntent` 作为唯一契约**。schema：`{intent: aggregate|trend|ranking|detail, metrics: [code], dimensions: [code], time_range: {type, relative|absolute, granularity}, filters: [{field, op, value}], ordering: {field, direction, limit}}`。与 `agent-eval-harness.golden_spec` 完全一致，评测即测节点输出。
- **决策 2：`metric_definition` 表按文档 3.4 DDL 落地，并加 `source_table`**。`metric_code UNIQUE`、`business_definition`、`formula`（可执行的 SQL 表达式）、`dimensions JSON`、`time_granularity`、`owner`、`version`、`status` + 新增 `source_table`（`metric_daily`/`user_behavior_fact`/`play_detail`），合成器据此选表（如 TopN 用例走明细聚合）。
- **决策 3：合成器规则化而非模板化**。不沿用被删的 `sql-templates.yml`；合成器按 intent 组装：SELECT 指标表达式 FROM source_table + WHERE filters + GROUP BY dimensions + 时间区间 + ORDER/LIMIT。输出可被 `SQL_HARD_GUARD` 复验。
- **决策 4：解析失败降级，而非强澄清**。`SEMANTIC_RESOLVE` 输出 `confidence` 与 `coverage`；低置信/无候选时由条件边降级到 `SQL_GENERATE`（raw LLM SQL + 护栏 + 重试），保证长尾可用。替代方案（interrupt 澄清）被否：与实习重复，且本版目标不是交互。
- **决策 5：相对时间在解析时展开**。`time_range.type=relative` 由解析器按当前日期展开成绝对区间（评测时按固定 `eval_date`），与比较器容差规则（长度差 ≤ 1 天）配套。
- **决策 6：DDL 收编 `schema.sql`**。所有 mock 表建表语句统一进 `schema.sql`，`DataInitializer` 只负责种子数据，消除"幽灵表"。

## Risks / Trade-offs

- [指标公式是手写 SQL 表达式，可能写错] → 每个指标配单测：给定 intent 合成 SQL 后由 `SqlParserValidator` 解析 + golden 断言。
- [LLM 解析质量不稳定（指标选错）] → 由 `agent-eval-harness` 的口径正确率持续度量；本版先保证 schema 与降级路径正确。
- [降级路径与语义路径行为不一致] → 明确降级时记录 `source=fallback` 到 state/审计，评测可区分统计。
- [`metric_daily` 只支持 category×日粒度] → TopN/creator 维度走 `source_table=user_behavior_fact` 实时聚合；周/月预聚合列为后续扩展。

## Migration Plan

1. Java：`metric_definition` DDL + 种子指标（扩到 6~8 个）+ `MetricCatalogService` + `/internal/metrics/{code}`；DDL 收编 `schema.sql`。
2. Python：`ResolvedIntent` schema（`state.py`）+ `SEMANTIC_RESOLVE` 节点 + prompt + `SQL_SYNTHESIZE` 合成器。
3. 图：接入 resolve/synthesize 节点与降级条件边；保留 `SQL_GENERATE` 作为 fallback。
4. 测试：合成器单测（同 intent 同 SQL）、解析 prompt 冒烟、降级路径测试；`pytest` + `mvn test` 全绿。
5. 联调：真实链路跑通语义路径与降级路径。

## Open Questions

- 指标种子集最终定哪几个（建议：播放量/播放时长/点赞/评论/分享/完播率/互动率）。
- `metric_definition.formula` 直接存可执行表达式，还是存"口径说明 + 合成规则"分离（默认：两者都存，formula 为可执行表达式）。
