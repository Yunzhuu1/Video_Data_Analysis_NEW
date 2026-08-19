## Why

合成器 v1 硬编码单指标（`len(metrics) != 1 → SynthesisError`），导致**多指标 NL 查询固定降级 raw SQL**：实测 n01/n02/n03（multi_metric）全部 `sql_source=fallback`——确定性语义链路的唯一结构性缺口。"播放量+点赞量同查"是 ChatBI 常见需求，降级 raw SQL 意味着绕开门禁语义层/合成确定性，是产品能力短板。

## What Changes

- **同源表多指标聚合（MVP）**：`synthesize()` 支持多个指标**经 `_resolve_path` 后全部落在 metric_daily 列路径**（同一 FROM + 多 SELECT 表达式列，共享 group-by/time/filter）——n01「统计各分类的播放量和点赞量」从 fallback → semantic；事实路径（按 dims 路由到 user_behavior_fact）多指标明确降级（各指标 factEventFilter 不同会致空结果）。
- **约束（防错误合成）**：多指标共享同 dimensions/time_range/filters/ordering（同 group-by 集）；intent 限 aggregate/trend（ranking/detail 多指标仍降级）；**非 metric_daily 列路径**多指标（跨源如 n02、或事实路径）**明确降级**（诚实边界，标注非目标）。
- **SUM 包裹复用**：metric_daily 且分组粒度 ≠ {date, category} 时，多指标每列各自 SUM（复用 v1 逻辑）。
- **评测**：--memory off N=45 回归中 n01 从 fallback → semantic 且 L1 正确；n02 保持 fallback（已知边界）；零回退。

## Capabilities

### New Capabilities
- （无新 capability，属既有语义层能力扩展）

### Modified Capabilities
- `semantic-resolution`: 「SQL 由确定性合成器生成」扩展——支持同源表多指标聚合（共享 group-by），跨源表多指标明确降级。
- `agent-eval`: 「评测数据覆盖」补充多指标用例的语义路径验证（n01 从 fallback → semantic，n02 边界标注）。

## Impact

- `agent-engine/app/synthesis/sql_synthesizer.py`：多指标合成（~60 行扩展）。
- `agent-engine/tests/test_sql_synthesizer.py`：多指标单测（同源聚合/跨源降级/约束校验）。
- `docs/metrics-report.md`：多指标解锁记录；`docs/开发日志.md`。
- Java：无改动（合成在 Python 侧）。
