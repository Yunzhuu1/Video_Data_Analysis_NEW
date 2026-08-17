## Why

语义解析（SEMANTIC_RESOLVE）当前每问必调 LLM，三个可量化问题：同问不同答（prompt 抖动破坏确定性）、重复消耗（真实评测 p50≈13s，LLM 调用占大头）、无沉淀（成功解析路径 question→ResolvedIntent 未落库，换说法可能降级 raw SQL）。

评测现状：端到端 95.65%、L1-L4 100%、拦截率 100%——**记忆系统定位为稳定性/成本/成长性增强，不是正确率修复**；验收以"开启记忆后正确率不回退 + 稳定性/延迟/命中率提升"为准。

## What Changes

- **MemoryStore（agent-engine 本地 SQLite，零新依赖）**：沉淀成功语义路径的 `规范化问题 → ResolvedIntent`；带指标 catalog 校验与解析规则版本（**内容哈希，防忘 bump**），口径/规则变更自动失效。
- **Retriever 接口 + TextSimilarityRetriever（stdlib 相似度，双阈值保守起步）**：
  - `≥0.95`（命中）→ **缓存直通**：跳过 LLM，复用存储 ResolvedIntent（`sql_source=memory`）——同问同答 100% 一致、token 归零、延迟毫秒级；**直通前做 metrics 一致性轻校验**（问题文本匹配 catalog metricName → 与存储 metric_codes 比对，不一致降级 inject/miss，防"最近7天点赞量"误命中"播放量"记忆）。
  - `0.85~0.95`（近命中）→ **few-shot 注入**：历史 (question→intent) 示例注入语义 prompt，LLM 照常解析。
  - `<0.85`（未命中）→ 现状。
- **写入路径**：仅"全链路成功"（执行成功 + DQ 通过/警告 + 语义路径）才写；只存 ResolvedIntent 不存 SQL（记忆永远不直接进 SQL）。
- **可观测性**：`AnalyzeResponse` 增加 `memoryHit`/`memoryBand` 字段（debug 透传）。
- **评测**：`--memory off|on`（默认 **off**，回归隔离）；`--memory on` 用**独立记忆库**（:memory:/临时文件，跑完即弃）；新增"重复问题对"用例（同问同答一致率 100%，**口径：两遍都成功解析的对**）+ **相似反例**（"最近7天点赞量"不得命中"播放量"记忆）+ 命中率/延迟/token 指标；**直通与 few-shot 指标分开看**（直通看一致率/延迟，few-shot 看命中率/L1-L4）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `semantic-resolution`: 语义记忆（检索直通/few-shot 注入/写入条件/失效）——见 delta spec。
- `agent-eval`: 记忆行为评测（回归隔离/重复对/相似反例/命中率）。

## Impact

- **Python**：新增 `app/memory/`（store/retriever/版本校验/metrics 一致性）；`app/graph/nodes.py`；`app/graph/state.py`（`sql_source` 增 `memory`）；`app/api/schemas.py`（`memoryHit`/`memoryBand`）；`app/prompts/semantic.py`（few-shot 注入）；`app/eval/runner.py`（`--memory`、重复对、反例、命中率）；`app/settings.py`。
- **Java**：无改动（`sqlSource` 已字符串透传）。
- **验证**：Python pytest + ruff；真实评测（--memory off 回归 + --memory on 重复对/反例）。
- **非目标**：向量检索实现（Retriever 接口预留）、AST 模板聚类、指标别名自动学习、用户偏好、LangMem、多租户隔离、记忆淘汰策略（MVP 只累计 hit_count）。

