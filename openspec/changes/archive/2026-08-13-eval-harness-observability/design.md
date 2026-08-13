## Context

真实 LLM 评测（deepseek-v4-flash + 真实 MySQL，2026-08-13）L1=84.62%。比对 MySQL `agent_run` trace 与评测报告发现 BUG-005：等待审批路径观测数据丢失。

数据流现状：

```text
Python 引擎 (routes.py AnalyzeResponse)
  status / finalReport / approvalReason / resolvedIntent / sqlRetryCount
    ↓ langGraphClient.analyze()
Spring AgentController.analyze
  ├─ 正常路径: finalReport → AnalysisReport；includeDebug=true 时组装 debug{resolvedIntent, sqlRetryCount}
  └─ WAITING_APPROVAL: 提前 return waitingApprovalReport()（只有 summary/recommendations，无 status、无 debug）
    ↓
eval runner run_real_case: payload.get("status") 恒为 null → 全部记 SUCCESS；resolvedIntent 恒为 null → L1 误算 0
```

根因：等待审批分支丢弃了 `status` 与 `resolvedIntent`；且 `sql_source` 从未进入引擎响应。

## Goals / Non-Goals

**Goals:**
- 等待审批响应可观测：status=WAITING_APPROVAL + resolvedIntent 透传到评测端。
- 真实模式报告 Source 列有值（sql_source 透传）。
- 重跑真实评测后：c18 判 PASS；c04/c08 的 L1 如实计入；报告 status 列与 agent_run 一致。

**Non-Goals:**
- 硬护栏误报/漏报调查（c04/c08/c21 误报、c19 漏报）——另开 change。
- 语义层 dimensions 抽取优化——另开 change。

## Decisions

### D1: status 作为 AnalysisReport 一级字段
`AnalysisReport` 增加可空 `status` 字段：正常路径置 `SUCCESS`，等待审批路径置 `WAITING_APPROVAL`。
- 备选：仅塞进 debug map → 拒绝。status 是响应的一级元数据，AnalysisReport 是统一信封，runner 直接读 `payload.get("status")` 语义最清晰，未来前端也可用。

### D2: 等待审批路径也组装 debug
`AgentController.analyze` 的等待审批分支在 `includeDebug=true` 时同样组装 `debug{resolvedIntent, sqlRetryCount, sqlSource}`，与正常路径一致。这要求 `EngineAnalyzeResponse` 增加 `sqlSource` 字段（引擎本就返回 status/resolvedIntent，仅 sqlSource 缺失）。

### D3: sql_source 全链路透传
```text
Python AnalyzeResponse 增加 sqlSource=state.get("sql_source")
  → Java EngineAnalyzeResponse 增加 String sqlSource
  → AgentController debug.put("sqlSource", ...)
  → runner run_real_case: state["sql_source"] = debug.get("sqlSource")
```
- 备选：runner 从 trace/agent_run 反查 → 拒绝，跨栈额外查询复杂且脆弱。

### D4: runner 状态构造修正
`run_real_case` 的 state 增加 `sql_source` 键；`status`/`approval_status` 直接取自 payload.status（等待路径现在有值）。

## Risks / Trade-offs

- [AnalysisReport 新增 status 字段影响既有 Java 测试] → 同步更新 `AnalysisReportMappingTest`，补等待路径透传测试。
- [Python AnalyzeResponse 加 sqlSource 影响 pydantic 契约] → 更新 `test_api_routes`，其余字段保持兼容（增量字段，非破坏）。
- [真实评测重跑耗时（约 20 分钟）且依赖 DeepSeek 余额] → 先用单元测试覆盖透传逻辑，真实重跑作为最终验收。
- [等待路径 finalReport 仍缺 metrics/charts（查询未执行）] → 属预期：e2e 判 FAIL 正确反映"未完成"，但 L1（语义）不再被误伤。

## Migration Plan

1. Java：AnalysisReport + EngineAnalyzeResponse 加字段，AgentController 等待分支补 debug，正常分支补 status/sqlSource。
2. Python：schemas.py + routes.py 加 sqlSource。
3. runner：run_real_case 读 status/resolvedIntent/sqlSource。
4. 单测 + 重跑真实评测验证，报告与开发日志入库。
