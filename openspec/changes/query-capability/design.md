## Context

scale-data（C1）后：指标 15、表 16、N=57 基线。两个生产查询能力缺口：
1. **指标值过滤**：合成器 filters 只支持维度过滤（WHERE category=美食）；"完播率>50%"（过滤聚合值）无法处理 → 这类查询要么 LLM 降级要么答错。
2. **跨源多指标**：n02（play_detail + fact）固定降级；C1 后跨表收益/比率组合查询变多。

约束：Python 主链路改动集中合成器（纯函数）；Java 零改动；R1 独立真值验证。

## Goals / Non-Goals

**Goals:**
- 指标值过滤（HAVING）合成；跨源同粒度多指标（子查询 JOIN）合成，n02 解锁。
- LLM prompt / 契约 / 比较器同步；新用例评测。
- 既有 N=57 基线零回退。

**Non-Goals:**
- 不做跨源异粒度多指标（一个按 category、一个按 content）——显式降级。
- 不做 ranking + 指标过滤组合（topN where 指标>X）——MVP 限 aggregate/trend。
- 不做数值过滤的多重嵌套/子查询优化（评测量小，可接受性能）。

## Decisions

### D1：指标值过滤（HAVING）
- **判定**：`filters[].field` 是 `metric_defs` 的指标 code → 指标过滤（HAVING）；是维度 code → WHERE。
- **合成**：`HAVING <agg_expr> op value`——agg_expr = 该指标的聚合表达式（同 SELECT 的 agg_expr，如 `COUNT(CASE WHEN event_type='play' THEN 1 END)`）；op ∈ {>, >=, <, <=}。
- **无 GROUP BY**：MySQL 允许 HAVING 无 GROUP BY（等价聚合后过滤）。
- **多指标过滤**：多个 HAVING 条件 AND。
- 边界：MVP 限 intent ∈ {aggregate, trend}（ranking + 指标过滤留后续）。

### D2：跨源同粒度多指标（子查询 JOIN）
- **条件**：metrics 来自不同 sourceTable + 共享 dims/time/filters/ordering + 各指标在自身表内可聚合到同一组维度键。
- **方案**：对每个指标生成子查询 `SELECT <dim_keys>, <agg_expr> AS <code> FROM <source> [JOIN...] WHERE ... GROUP BY <dim_keys>`，再按维度键 JOIN：
  ```sql
  SELECT a.category AS category, a.completion_rate, b.engagement_rate
  FROM (SELECT cd.category, AVG(pd.completion_rate) AS completion_rate
        FROM play_detail pd GROUP BY cd.category) a
  JOIN (SELECT cd.category, <engagement公式> AS engagement_rate
        FROM user_behavior_fact ubf JOIN content_dim cd ... GROUP BY cd.category) b
       ON a.category = b.category
  ```
- **维度键**：dims +（trend 时 date）。
- **跨源 vs 同源 fact 优势**：各子查询独立带自己的 eventFilter（play/like 互不冲突）——这就是"跨源能解、同源 fact 多指标会空结果"的本质区别。
- **约束（防错）**：任一指标无法按维度键聚合（粒度不对齐）→ SynthesisError 降级。

### D3：LLM prompt / 契约 / 比较器同步
- `filters[].op` 扩展（契约 Literal 含 >、>=、<、<=）。
- **prompt 规则**：区分"维度过滤"（category 等 → WHERE）与"指标过滤"（指标名+超过/高于/低于 → 指标 code + op 比较）。
- **比较器**：filters 三元组比较支持新 op（归一化后 field/op/value 逐项比）。

### D4：评测
- 新增 ~4 数值过滤用例（"完播率超过50%的创作者"等，aggregate/trend）。
- n02 预期从 fallback → semantic（R1 真值重取）。
- 新用例独立手工 SQL 取真值（R1 防自我确认）。
- 回归：--memory off N=57 基线零回退（既有 45 R1 稳定）。

## Risks / Trade-offs

- **[Risk] HAVING 误用于维度/非聚合** → 指标过滤限定 field 必须是指标 code；维度过滤走 WHERE。
- **[Risk] 跨源 JOIN 粒度不对齐 → 错数据** → 显式约束（维度键必须一致可聚合），不满足即 SynthesisError。
- **[Risk] 子查询性能**（评测量小）→ 可接受；生产优化留后续。
- **[Risk] LLM 误判指标 vs 维度过滤** → prompt 规则 + 解析不出（低置信）走 fallback。

## Migration Plan

1. 合成器：指标值过滤（HAVING）→ 跨源多指标（子查询 JOIN）+ 单测。
2. prompt / 契约 / 比较器同步 + 单测。
3. cases.yaml：数值过滤用例 + n02 预期改 semantic + R1 真值。
4. 全量 pytest + ruff → --memory off N=57 回归（零回退）+ R1。
5. metrics-report + 开发日志。

## Open Questions

- ranking + 指标过滤（"完播率>50% 且播放量 top5"）→ 留后续（当前降级）。
- 跨源 JOIN 的维度键含 content/creator 时的对齐 → 按 C1 新表维度键（content_id/creator_id）直接 JOIN，验证后定。
- HAVING 与 WHERE 的混合（维度过滤 + 指标过滤）→ 都支持（WHERE 前置 + HAVING 后置）。
