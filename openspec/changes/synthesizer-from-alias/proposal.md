## Why

真实评测修复观测（Source 列）后暴露 BUG-006：确定性 SQL 合成器产出 `SELECT ... FROM md ...`，使用表别名（`_ALIAS: metric_daily→md`）但 FROM 子句只写别名、未声明 `FROM metric_daily md`，MySQL 报 `Table 'md' doesn't exist` → 执行/验证失败 → 全量降级 raw LLM。**语义合成路径在真实库上从未生效过**（L1=100% 说明语义解析正常，纯合成环节 bug），合成 SQL 的实际价值被完全浪费。

## What Changes

- **合成器 FROM 子句修复**：`sql_synthesizer.py` 的 `synthesize()` 在 SELECT 的 FROM 子句中输出 `FROM {source} {alias}`（真实表名 + 别名声明），所有 source 分支（metric_daily / user_behavior_fact / play_detail）与 JOIN 场景统一。
- **可执行性测试**：新增/增强单元测试，断言合成 SQL 含真实表名与别名声明，且能在真实 schema（MySQL）上解析执行。
- **回归**：Python pytest + ruff 全绿。
- **（可选）真实评测重跑**：验证 Source 列出现 `semantic`、端到端成功率提升。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `semantic-resolution`: 「SQL 由确定性合成器生成」需求新增场景——合成 SQL SHALL 引用真实表名并声明别名，可在真实库上执行（不再因 `FROM md` 类未声明别名而失败降级）。

## Impact

- **Python**：`agent-engine/app/synthesis/sql_synthesizer.py`（FROM 子句）、相关测试。
- **评测**：Source 列应从全 `fallback` 变为出现 `semantic`；端到端成功率/延迟预期改善。
- **验证**：Python pytest + ruff；真实评测重跑（可选，需 DeepSeek 余额）。
- **非目标**：护栏误报/漏报（c04/c10 误报、c18/c19 漏报）、dimensions 抽取优化、多指标合成支持。

