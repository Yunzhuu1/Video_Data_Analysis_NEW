## 1. 数据模型与指标字典（Java）

- [ ] 1.1 `schema.sql` 收编全部 mock 表 DDL（user_behavior_fact/content_dim/creator_dim/user_dim/time_dim/activity_dim/metric_definition/metric_daily/play_detail）
- [ ] 1.2 落地 `metric_definition` 表（对齐文档 3.4 DDL + `source_table` 列），`DataInitializer` 种子扩到 6~8 个指标（播放量/播放时长/点赞/评论/分享/完播率/互动率）
- [ ] 1.3 新增 `MetricCatalogService`（findByCode/search）+ `InternalMetricController`（`/internal/metrics/{code}`）
- [ ] 1.4 `MetricQueryTool` 迁移为 `MetricCatalogService` 调用或删除（随 `legacy-cleanup` 节奏处理）

## 2. 语义解析（Python）

- [ ] 2.1 `state.py` 新增 `ResolvedIntent` 类型（intent/metrics/dimensions/time_range/filters/ordering），与 `golden_spec` 同构
- [ ] 2.2 新增 `semantic_resolve_node`：调用 LLM 输出 `ResolvedIntent` JSON + confidence/coverage；相对时间按当前日期展开
- [ ] 2.3 新增语义解析 prompt（`app/prompts/semantic.py`）：只允许使用 `metric_definition` 中的指标/维度，输出严格 JSON
- [ ] 2.4 `PlatformClient` 增加 `/internal/metrics/{code}` 调用，resolve 前拉取指标定义作为上下文

## 3. 确定性合成（Python）

- [ ] 3.1 新增 `SQL_SYNTHESIZE` 节点/合成器：按 intent 组装 SELECT（指标表达式 + source_table + filters + group by + 时间区间 + order/limit）
- [ ] 3.2 合成器单测：同意图同 SQL；TopN 走明细聚合；对比类生成 `IN` 过滤
- [ ] 3.3 合成 SQL 必须能通过 `SQL_HARD_GUARD`（新增集成断言）

## 4. 图接入与降级

- [ ] 4.1 `graph_builder.py` 接入 `SEMANTIC_RESOLVE → SQL_SYNTHESIZE → SQL_HARD_GUARD`，`SQL_GENERATE` 保留为 fallback
- [ ] 4.2 降级条件边：resolve 低置信/无候选 → `SQL_GENERATE`，结果标记 `source=fallback`
- [ ] 4.3 测试：语义路径、降级路径、合成失败回退，`pytest` 全绿

## 5. 验证与文档

- [ ] 5.1 `mvn test` + `pytest tests` + `ruff` 全绿
- [ ] 5.2 真实联调：语义路径（各分类播放量趋势）与降级路径（开放问题）各跑通一次
- [ ] 5.3 更新架构文档/接口契约/AGENTS.md 中"语义解析 + 确定性合成"章节
