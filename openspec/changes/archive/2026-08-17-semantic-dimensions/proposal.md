## Why

真实评测 L4 dimensions 61.54%（8/13）是语义层最弱项，拖累 L2 严格全字段（61.54%）。根因数据（最新评测 5 个失分用例）显示两类确定性模式：
1. **漏维度**（c01/c07）："各分类...趋势"、"对比 A 和 B 分类...趋势" → 应为 `dimensions=[category]`，解析成空；
2. **多维度**（c03/c12/c13）：时间序列问题（"最近7天每天播放量"等）把 `date` 塞进 `dimensions`——date 应属 `time_range.granularity`，不是业务维度（DIMENSIONS 含 date 导致 LLM 误判）。

非随机波动，是 prompt 规则缺失 + date 语义边界不清。

## What Changes

- **根因数据落库**：确认 5 个失分用例的 resolvedIntent 差异（漏 category / 误塞 date）。
- **Prompt 优化**：`SEMANTIC_SYSTEM_PROMPT` 强化三类规则——
  - `date` 是时间粒度（`time_range.granularity`），**不得进 dimensions**；
  - "各分类/按分类/每类" → `dimensions=[category]`（不是 filter）；
  - "美食类/游戏的视频" → `filters=[category=...]`（不是 dimension）；
  - 补趋势+维度、时间序列 的正反示例。
- **确定性兜底（design 评估）**：对已知模式做轻量后处理——dimensions 含 `date` 时移除（移入 granularity 判定）；含"各分类"且 dimensions 为空时补 `category`。防过拟合：只补高置信模式，以评测为准。
- **评测验证**：真实评测 L4 dimensions ≥85%、L2 ≥70%。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `semantic-resolution`: 「LLM 只做语义匹配」需求补维度抽取规则场景（date 不得入 dimensions、"各分类"→dimensions、类目限定→filters）。

## Impact

- **Python**：`app/prompts/semantic.py`（system prompt 规则 + 示例）、`app/agents/semantic_resolver.py`（normalize 后处理兜底，可选）。
- **评测**：`docs/eval-report.md`（重跑快照）、`docs/开发日志.md`。
- **验证**：Python pytest + ruff；真实评测重跑（--llm real --platform mock 先验证语义层，再 real+real 出 L2/L4）。
- **非目标**：多指标合成、门禁规则、记忆系统、回答质量（已闭环）。

