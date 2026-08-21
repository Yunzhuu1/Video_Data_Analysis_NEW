## Why

指标目录已从 7 个扩展到 15 个，继续把完整目录塞进语义解析 Prompt 会让输入随指标规模线性增长，并增加相似指标互相干扰的概率；现有真实评测已观察到扩容后的单轮 L1 波动。现在需要在 LLM 前增加可评测、可回退的指标候选召回层，使目录继续扩张时语义解析仍保持稳定，而不是依赖更长 Prompt。

## What Changes

- 在 `SEMANTIC_RESOLVE` 前增加确定性的 `MetricCandidateRetriever`：按指标 code/名称、最长别名匹配和中文字符 n-gram 词面分数召回 Top-K 指标。
- 召回不依赖 embedding API；无可靠信号、候选不足或召回异常时回退完整 catalog，避免因裁剪目录静默漏指标。embedding 仅保留为后续可选增强，不属于本 change。
- 多指标问题保留全部被显式名称/别名命中的指标；LLM Prompt 只消费候选 catalog，并记录候选、分数、命中原因、召回模式及是否回退。
- 增加离线召回评测和真实 LLM A/B：同时报告传统 `recall@configured_k` 与 pinned-aware `strict_recall@effective_k`，以后者和 effective recall 作为正确性门槛，再比较完整 catalog 与 Top-K 的 L1-L4、旧 57 例回归、Prompt 体积/token 和降级率。
- embedding 额度不足不阻塞本轮开发和评测；真实评测使用 `--memory off`，只验证词面召回 + LLM 语义解析链路。

## Capabilities

### New Capabilities

- `metric-recall`: 基于 catalog 与别名表的确定性指标候选召回、Top-K 裁剪、安全回退和运行时观测契约。

### Modified Capabilities

- `semantic-resolution`: `SEMANTIC_RESOLVE` 从消费完整 catalog 改为优先消费召回候选，并在无可靠召回时使用完整 catalog。
- `agent-eval`: 增加 `recall@configured_k` / `strict_recall@effective_k`、多指标全量召回、完整 catalog/Top-K A/B、Prompt 体积与既有子集回归报告。

## Impact

- Python Agent Engine：新增指标召回模块，修改 `semantic_resolve_node`、state/debug 观测字段及语义 Prompt 调用入口。
- 评测：两个离线 recall 指标都只复用 `cases.yaml` 中含 `golden_spec.metrics` 的 **49 条 judged cases（分母=49）**；端到端 A/B 使用全量 N=61，既有 N=57 子集单独报告，禁止混用分母或隐藏 pinned 扩容。
- 配置：新增 Top-K、词面阈值和全目录回退开关；默认值必须经离线数据标定后固化。
- 数据/API：不改数据库表或业务响应；Agent 内部响应与 Spring `includeDebug=true` 通道增量透传召回观测字段。指标定义继续以 `metric_catalog.json` / 平台 catalog 为唯一来源。
- 依赖：不新增在线模型或分词服务依赖。
