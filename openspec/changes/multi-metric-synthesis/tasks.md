## 1. 合成器多指标

- [x] 1.1 `synthesize()` 支持同源表多指标聚合：**全部 metrics 经 `_resolve_path` 后 `path.source == "metric_daily"`** 且 intent ∈ {aggregate, trend} → 单 FROM + 多 SELECT 列（每列 `agg_expr AS code`，无 spurious JOIN），SUM 包裹按统一 gb 判断
- [x] 1.2 约束校验：非 metric_daily 路径多指标（跨源 / 事实路径，如 trend+dims=[content] 的播放+点赞）/ 多指标 ranking|detail / 维度时间过滤排序不一致 → SynthesisError（显式降级）
- [x] 1.3 单测：n01 同源聚合 SQL 形态与 SUM 包裹、跨源降级（n02）、ranking 多指标降级、单指标行为不变

## 2. 评测与回归

- [x] 2.1 Python pytest + ruff 全绿
- [x] 2.2 --memory off N=45 回归：n01 sql_source=semantic 且 L1 正确；n02 仍 fallback（边界标注）；整体零回退
- [x] 2.3 metrics-report 更新（多指标解锁 + n02 边界）；开发日志追加

## 3. 收尾

- [ ] 3.1 全量终验（pytest + ruff）；提交并推送分支
