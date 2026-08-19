## Why

指标 ID 是语义层的唯一锚点（企业实践共识：澄清结果只需找到指标 ID 即可走下游）。但当前 `metrics_consistent` 校验用**字符串包含匹配** catalog 指标名，实测缺口：cases.yaml **9/44** 匹配不到指标名，其中**可判定（有 golden_spec）5 个**（c07/n19/n20/n23/n25）会被一致性校验拦（c18/c19/c22/c20 为 detail/risk/open 无 golden，不影响 L1）；synonym **22/35**（63%，hard 层 73%）匹配不到。后果：c07 类直通被保守拦截（real-session 7/8 的"缺 1"）、难层注入 0 收益的机制根因（hard 层匹配不到 → 语义距离远 + 一致性校验拦）。本 change 用「指标表达映射」（别名配置 + 自学习指纹）补上"自然语言表达 → 指标 ID"的确定性通道。

## What Changes

- **`aliases.yaml` 静态别名表**（人工审核沉淀，同 metric_catalog 模式）：高频确定性表达（播放走势/观看量/完播情况 → 指标 ID），评测驱动补充。
- **读取侧扩展**：`extract_metric_names` / `metrics_consistent` 在 catalog 精确名之外，按别名表匹配；`metrics_consistent` 双保险保留（别名只扩展"能判定"，不绕过校验）。
- **指标 ID 表达指纹（可选增强）**：`MetricIdFingerprint` 从写路径沉淀的 norm_question 按 `metric_codes` 归属自动派生每个 ID 的表达集，模糊匹配兜底别名未覆盖的动态表达；阈值标定后启用。
- **虚拟澄清实验（0.5 天，价值上限量化）**：评测内定义"歧义判定"（低置信/多指标候选），用 golden 自动模拟用户选择，产出**潜在澄清率（拆「歧义且错」/「歧义但对」）/ 虚拟澄清收益 / 澄清率随记忆下降曲线（按 band 分层，只统计 hit/inject 可达项）**——量化"若存在完美澄清"的正确率上限，**明确不做真 HITL**（用户决策）。
- **评测目标**：real-session 7/8 → 8/8（c07 解锁）；毒化反例仍拦；--memory off N=45 零回退；synonym 难层 band 分布变化（hard 层部分 miss → inject/hit）。

## Capabilities

### New Capabilities
- `metric-alias`: 指标表达映射——静态别名表 + 自学习指纹，把"自然语言表达 → 指标 ID"确定性化；含虚拟澄清实验协议。

### Modified Capabilities
- `semantic-resolution`: 「语义记忆检索与写入」的 metrics 一致性校验扩展——匹配不再依赖字符串包含指标名，支持别名/指纹表达映射。
- `agent-eval`: 新增指标表达覆盖用例（每个别名至少 1 个 golden/同义用例）与虚拟澄清指标（潜在澄清率/澄清收益/澄清率下降）。

## Impact

- `agent-engine/app/memory/aliases.py`（新）：AliasStore 加载/匹配。
- `agent-engine/app/memory/metric_ids.py`（新）：MetricIdFingerprint（可选增强）。
- `agent-engine/app/memory/retriever.py`：`extract_metric_names` / `metrics_consistent` 接别名 + 指纹。
- `agent-engine/app/eval/aliases.yaml`（新）：别名表。
- `agent-engine/app/eval/runner.py`：虚拟澄清实验（歧义判定 + golden 模拟选择）。
- `agent-engine/app/graph/nodes.py`：调用点传别名/指纹。
- 单测 + 阈值标定脚本；`docs/metrics-report.md`（表达映射价值 + 虚拟澄清数字）；`docs/开发日志.md`。
- Java：无改动（语义层在 Python 侧）。
