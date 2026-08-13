## Why

真实 LLM 评测（deepseek-v4-flash + 真实 MySQL，2026-08-13）跑通后 L1=84.62%，但通过比对 MySQL `agent_run` trace 与评测报告发现评测 harness 存在观测缺口（BUG-005）：等待审批（WAITING_APPROVAL）路径不透传 `status` 与 `resolvedIntent`，导致评测结果无法如实反映系统行为——c18 实际正确触发审批却被误判 FAIL，c04/c08 的 L1 被误算为 0。观测失真会让基线数字失真，进而误导后续优化决策。

## What Changes

- **Java 等待审批响应透传**：`AgentController.analyze` 对 WAITING_APPROVAL 返回的 `AnalysisReport` 携带 `status=WAITING_APPROVAL`，并透传引擎返回的 `resolvedIntent`（必要时调整 `EngineAnalyzeResponse` / `AnalysisReport` DTO）。
- **eval runner 真实模式观测**：`app/eval/runner.py` 的 `run_real_case` 正确读取 `status` / `resolvedIntent` / `sqlSource`，计入用例结果与报告。
- **报告 Source 列修复**：真实模式报告 Source 列不再恒为 `-`，透传 `sql_source`。
- **文档入库**：更新 `docs/eval-report.md` 与 `docs/开发日志.md`，记录 BUG-005 修复与验证。

## Capabilities

### New Capabilities

无（不引入新能力）。

### Modified Capabilities

- `agent-eval`: 真实模式评测 SHALL 能观测等待审批状态与语义解析结果（status/resolvedIntent/sql_source），使报告如实反映系统行为。

## Impact

- **Java**：`AgentController.java`、`EngineAnalyzeResponse`/`AnalysisReport` DTO（等待审批路径）。
- **Python**：`agent-engine/app/eval/runner.py`（`run_real_case` 状态构造）。
- **评测报告**：`docs/eval-report.md`、`docs/eval-reports/*.json`（status/source 列）。
- **验证**：Python pytest + ruff、Java `mvn test`、真实评测重跑（需 DeepSeek 余额）。
- **非目标**：硬护栏误报/漏报调查（c04/c08/c21 误报、c19 漏报）、语义层 dimensions 抽取优化，另开 change。
