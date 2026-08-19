## Context

合成器 v1（`app/synthesis/sql_synthesizer.py`，202 行）入口校验 `len(metrics) != 1 → SynthesisError` → 节点降级 raw SQL。catalog 7 个指标分 3 个源表：metric_daily（5 个：total_plays/play_duration/likes/comments/shares）、play_detail（completion_rate）、user_behavior_fact（engagement_rate）。多指标用例 n01（total_plays+total_likes，同源 metric_daily）、n02（completion_rate+engagement_rate，跨源）、n03 实测全部 fallback。

## Goals / Non-Goals

**Goals:**
- 同源表多指标聚合（metric_daily）解锁：n01 从 fallback → semantic 且 L1 正确。
- 确定性不倒退：同意图同 SQL；失败仍降级（不抛未捕获异常）。
- --memory off N=45 零回退。

**Non-Goals:**
- 跨源表多指标（n02）合成——MVP 明确降级（子查询 JOIN 复杂度高、粒度对齐风险，留后续）。
- 多指标 ranking/detail（排序多指标、明细多指标）——MVP 降级。
- 指标间运算（差值/比值）——指标关系归语义层（metric_definition），不在合成器。

## Decisions

### D1：同源表多指标（MVP 必做，判定基于 _resolve_path 后的 source）
- **判定式（P1）**：全部 metrics 经 `_resolve_path(mdef, intent, dims)` 后 `path.source == "metric_daily"` 才合成多指标；否则（含经路由到 user_behavior_fact 的事实路径）一律降级。
  - 不能用原始 `sourceTable` 判同源：`_resolve_path` 会把 metric_daily 指标在特定 dims（如 trend+dims=[content]）下路由到 user_behavior_fact，且各指标 factEventFilter 不同（total_plays→`event_type='play'`、total_likes→`event_type='like'`）——若判"同源"会合成 `WHERE event_type='play' AND event_type='like'` → 空结果。
- 例 n01（metric_daily 列路径）：`SELECT md.category AS category, SUM(md.total_plays) AS total_plays, SUM(md.total_likes) AS total_likes FROM metric_daily md GROUP BY md.category`。
  - 注（P2）：metric_daily 的 category 维度返回 `md.category`，**不产生 JOIN**（content_dim 的 JOIN 只在 user_behavior_fact 源路径出现）。
- 每个 metric 的 expr = `_resolve_path(mdef, intent, dims)` 的 expr（metric_daily 路径下即 formula 列名）；SUM 包裹按统一 gb 判断（`gb != {date, category}` 时每列 SUM）。
- 理由：metric_daily 行粒度为 (date, category)，同 group-by 下多列聚合语义一致，风险最低；事实路径多指标（factEventFilter 兼容校验）留后续（P1 方案 2）。

### D2：非 metric_daily 路径多指标 → 明确降级
- 任一 metric 经 `_resolve_path` 后 source 非 metric_daily（跨源：play_detail/fact；或 metric_daily 被路由到事实路径）→ `SynthesisError`（走现有降级 raw SQL 路径）。
- n02 保持 fallback，报告标注「已知边界：跨源/事实路径多指标未支持」。
- 理由：completion_rate（play_detail AVG）与 engagement_rate（fact 聚合）粒度/聚合语义不同；事实路径各指标 factEventFilter 不同会导致空结果（P1）。子查询 JOIN 需严格对齐（date/category 双键），MVP 不做；面试可讲为「多指标 metric_daily 列路径优先、其余渐进」的策略。

### D3：约束校验（防错误合成）
- 多指标时 intent ∈ {aggregate, trend}；ranking/detail → SynthesisError。
- 多指标共享同 dimensions/time_range/filters/ordering（golden 已如此；若不一致 → SynthesisError）。
- 理由：同一 group-by 集才能单 FROM 聚合；约束显式失败优于产出错误 SQL。

### D4：单测与验证
- 单测：同源多指标聚合（n01 SQL 形态/SUM 包裹）、跨源降级（SynthesisError）、约束（ranking 多指标降级）、单指标行为不变。
- 真实评测：--memory off N=45 回归，n01 sql_source=semantic 且 L1 正确；n02 仍 fallback（边界标注）；零回退。

## Risks / Trade-offs

- **[Risk] SUM 语义对比率型指标（如完播率）不适用** → MVP 只解锁 metric_daily 同源（5 个指标均为可加量）；completion_rate 在 play_detail 单源路径，多指标含它即跨源 → 降级。
- **[Risk] 多指标列名冲突/别名** → 每列 `AS code`（与单指标一致），无冲突。
- **[Risk] 同源但不同公式语义**（total_plays 是列、未来指标是表达式） → `_resolve_path` 已统一返回 expr，扩展安全。

## Migration Plan

1. synthesize() 多指标分支（纯增量，单指标路径不变）。
2. 单测 + 全量 pytest + ruff。
3. --memory off N=45 回归（n01 semantic、n02 fallback、零回退）。
4. metrics-report + 开发日志；无部署（合成在 Python 侧，确定性输出）。

## Open Questions

- 跨源表多指标（n02）是否值得做子查询 JOIN 版？（倾向后续独立 change，需先确认 play_detail/fact 粒度可对齐）
- 多指标 trend 是否已支持？（支持，但**仅 metric_daily 列路径**——trend group-by 逻辑 `gb=[date]+dims` 与单指标相同，多指标只是加 SELECT 列；trend+dims=[content] 会触发事实路径 → 降级，见 P1）
