## Context

当前 `semantic_resolve_node` 每次从平台读取完整指标目录，并由 `SemanticResolver` 将所有指标的 code、名称、业务定义和维度拼入 Prompt。该方案在 7 个指标时简单有效，但 catalog 已扩展到 15 个；真实评测出现过扩容后 L1 单轮波动，且 Prompt 长度会随指标数线性增长。生产系统通常先做 schema linking / metric retrieval，再让模型在小候选集内解析。

本项目暂时没有可用的 embedding API 额度，因此本 change 必须在纯本地、确定性、无新增在线依赖的前提下完成。现有 `app/memory/aliases.py` 已实现最长别名匹配，但数据文件位于 `app/eval/aliases.yaml`，形成运行时反向依赖评测资产；C3 同时修正该依赖方向。

## Goals / Non-Goals

**Goals:**

- 在 LLM 前召回与问题相关的 Top-K 指标，降低目录规模对 Prompt 和语义解析稳定性的影响。
- 对显式多指标问法保证所有名称/别名命中项都进入候选，不因 K 截断。
- 以安全回退保证召回不确定时行为不劣于现有“完整 catalog”路径。
- 建立独立于 LLM 的 Recall@K 门禁，以及完整 catalog / Top-K 的真实 LLM A/B 口径。
- 让候选、分数、原因、模式和 Prompt 体积可观测、可审计。

**Non-Goals:**

- 不接入 embedding、向量库、外部分词服务或学习排序模型。
- 不做表/列级 schema linking；本轮只召回指标，维度清单仍完整提供。
- 不改变 `ResolvedIntent`、SQL 合成器、指标公式或数据库模型。
- 不把当前 N=61 的结果宣称为大规模生产泛化证明；它是小样本回归与方向性证据。

## Decisions

### D1：别名提升为运行时唯一数据源

将 `app/eval/aliases.yaml` 移至运行时资源目录（如 `app/resources/metric_aliases.yaml`），保留 `alias`、`metric_code` 和 `covered_by` 等覆盖元数据。统一 loader 的契约定死为 `load_alias_bundle() -> AliasBundle(alias_map, alias_records)`：`alias_map: dict[str, str]` 供 memory/recall 最长匹配，`alias_records: list[AliasRecord]` 供评测检查 `covered_by` 等元数据；既有 `get_aliases()` 仅作为返回 `bundle.alias_map` 的兼容投影。两者必须从同一次解析、校验和缓存产生，评测不得自行读取 YAML。重复 alias 指向不同 metric code 属无效资源，loader 明确报错。

指标候选表达集固定由以下字段组成：

1. `metricCode`；
2. `metricName`；
3. 该 code 对应的人工审核 alias。

`businessDefinition` 不进入词面表达集：其长文本包含大量共享业务词，容易把“播放”“用户”等泛词扩散到无关指标。catalog 仍是指标定义唯一来源，别名资源只是用户表达映射，不复制公式和血缘。

备选方案是在 `metric_catalog.json` 每项内直接增加 aliases；这更接近完整企业 catalog，但会要求 Java DTO/数据库/API 同步扩展。C3 先保持无数据库迁移，后续可把别名迁入指标管理服务。

### D2：固定为“精确/最长别名 + 字符 n-gram”确定性召回

新增纯函数式 `MetricCandidateRetriever`。输入是 `question + full_catalog + aliases`，输出 `MetricRecallResult`：

```text
ranked_candidates: [{metric_code, score, reasons, matched_expressions}]  # 回退前 Top-K/pinned 排名
prompt_catalog_codes: [metric_code]  # 实际给 LLM；full/full_fallback 时为完整目录
mode: topk | full | full_fallback
fallback: bool
fallback_reason: null | no_reliable_signal | invalid_catalog | retriever_error
top_k / lexical_threshold / full_catalog_count / prompt_catalog_count
```

处理顺序：

1. 规范化问题与表达：先做 Unicode NFKC，再 `lower()`，随后仅保留 `str.isalnum()` 为真的 Unicode code point；因此空白、标点和 metric code 中的 `_` 被移除（`total_plays` → `totalplays`），中文按 Python Unicode code point 处理。归一化后为空的表达直接丢弃，空问题不计算词面分；
2. 对 metricCode、metricName 和 alias 做子串匹配；表达重叠时按“更长表达优先”，同长度按 metric code 稳定排序；所有显式命中的 metric code 都设为 pinned；
3. 对每个指标计算其所有表达中的最高词面分。n-gram 使用归一化后 Unicode code point 的**集合**（不是多重集），`coverage_n(e,q) = |ngrams_n(e) ∩ ngrams_n(q)| / |ngrams_n(e)|`。当 `len(e) >= 2` 时，分数固定为 `0.35 * coverage_1 + 0.65 * coverage_2`；单 code point 表达没有 bigram，权重重归一后固定为 `coverage_1`，避免 0 分母；空表达已在步骤 1 丢弃，分数为 0。该口径不受问题附加时间/维度词长度稀释；
4. pinned 指标全部保留，再按 `(-score, metric_code)` 填充到 K。若 pinned 数量超过 K，返回全部 pinned，不截断真实多指标表达；
5. 没有 pinned 且最高词面分低于阈值时，不做强猜，回退完整 catalog。

默认候选 K 从 5 开始，词面阈值从 0.55 开始；apply 阶段仅对 N=61 中含 `golden_spec.metrics` 的 **49 条 judged cases（Recall 分母=49）**离线扫描标定并写死最终值。若 K=5 不能达到 judged golden metrics Recall@K=100%，增大 K 或对失败类型增加经审核 alias，不能以降低召回门槛掩盖漏召回。报告必须记录最终 K、阈值、表达数据版本和原始计数；其余 12 条无 golden case 不进入 Recall 分母。

选择字符 n-gram 而不是 `difflib`：它对中文无需分词、可解释、无网络依赖，并且表达覆盖口径不会因“最近 7 天……按分类”之类上下文变长而急剧降低。它不是语义模型，所以低信号时必须回退。

### D3：完整 catalog 用于校验，候选 catalog 只限制 LLM 搜索空间

运行顺序调整为：

```text
platform.metric_catalog() -> full_catalog
MetricCandidateRetriever(question, full_catalog) -> recall_result
memory pre-resolve(full_catalog, prompt_catalog)
  hit: 用 full_catalog 做 metrics 一致性/失效校验，直接复用 intent
  inject: few-shot + prompt_catalog 调 SemanticResolver
normal: prompt_catalog 调 SemanticResolver
```

`mode=topk` 时 `prompt_catalog` 取 `ranked_candidates`；`mode=full`（显式基线/回滚）或 `mode=full_fallback`（被迫回退）时取完整 catalog。`fallback` 仅在 `mode=full_fallback` 时为 true，显式 `full` 必须为 false 且不计入 fallback rate。可计算排名时，即使最终低信号回退，也保留回退前 `ranked_candidates` 供 strict Recall@K 审计；invalid/error 无法排名时该列表为空。这样候选裁剪不会削弱记忆命中的 catalog 一致性校验，也不会让已失效指标通过。召回异常只记录 warning 并回退完整 catalog，不允许打断主链路。

为支持 A/B，配置 `METRIC_RECALL_MODE=topk|full`：默认 `topk`，`full` 仅用于基线/紧急回滚。K 与阈值也进入 settings；线上无需修改请求协议。

### D4：回退是正确性边界，不是“召回失败”粉饰

以下情况必须使用完整 catalog：

- catalog 为空/条目缺少 code，召回器无法构建有效索引；
- 无显式命中且最高词面分低于标定阈值；
- loader、别名校验或召回计算抛异常；
- 配置显式指定 `mode=full` 时使用完整 catalog，但这是主动基线/回滚，结果为 `mode=full, fallback=false, fallback_reason=null`，不属于失败回退。

回退用例仍可正常由 LLM 解析，但单独计入 `metric_recall_fallback_rate`。不能把 full fallback 计作 Top-K 命中来夸大裁剪覆盖；离线指标同时报告：

- `strict_recall@K`：固定分母 49，检查每例**回退前 `ranked_candidates[:K]`**是否包含全部 golden metrics；full fallback 不因看到完整目录自动成功，显式 full 基线不参与该离线运行；
- `effective_recall`：包含 full fallback 后是否可见全部 golden metrics；
- fallback 原始计数和原因分布。

验收硬门槛为 effective recall 49/49，且 strict Recall@K 必须报告真实分子/49；任何实际 `mode=topk` 用例不得漏 golden metric。若某用例只能靠 full fallback 保真，要如实报告为“未裁剪覆盖”，不能用完整目录抬高 strict Recall@K。

### D5：观测字段走既有 debug 通道

`DataAgentState` 增加 `metric_candidates`、`metric_recall_mode`、`metric_recall_fallback`、`metric_recall_reason`、`metric_recall_top_k`、`semantic_prompt_chars`。其中 `metric_candidates` 是回退前排名，另记录实际 Prompt catalog 数量；`semantic_prompt_chars` **严格定义为实际发送给 LLM 的最终 user message 的 Python `len()`**：即 `len(build_semantic_user_prompt(question, prompt_catalog, dimensions, examples))`，不含 `SEMANTIC_SYSTEM_PROMPT`；normal 路径 `examples=None`，memory inject 路径包含实际注入的 examples。实现 SHALL 只构造一次该 user prompt，测量后把同一个字符串交给 LLM，避免“测量串”和“发送串”漂移。memory hit 等未调用语义 LLM 的路径记为 `null` 并从 Prompt 均值分母排除，不能记 0。full/topk A/B 必须使用同一 memory 协议；本轮固定 `--memory off`，因此两组均不含 examples。

Agent `/analyze` 响应和 Spring `includeDebug=true` 增量透传上述 camelCase 字段；默认业务响应不展示这些数据。

候选只记录 code、分数和原因，不记录用户问题之外的新敏感数据。分数保留固定小数位，候选顺序稳定，便于测试和面试演示。

### D6：评测先证明“没漏”，再观察“是否更好”

评测分三层：

1. **离线确定性门禁**：仅对 N=61 中含 `golden_spec.metrics` 的 49 条 judged cases 直接调用召回器（分母=49），输出 Recall@K、effective recall、多指标完整召回率、fallback 率和逐例候选；其余 12 条仅参与端到端 A/B，不进入 Recall 分母。该层不调用 LLM、embedding 或数据库。
2. **单元/回放回归**：验证最长匹配、稳定排序、pinned>K、低信号回退、异常回退、记忆 inject 使用候选 catalog，以及 debug 透传。
3. **真实 LLM A/B**：同一 N=61、`--platform mock --memory off`，A=`mode=full`，B=`mode=topk`。分别报告整体 N=61 和既有 N=57 子集的 L1-L4、sql_source、ERROR、fallback 原始计数。模型单轮存在随机性，真实 A/B 只作方向性观测；若 B 下降，必须逐例核查是否与漏召回相关，必要时复跑，不把单轮波动直接归因于召回。

Prompt 缩减的主指标使用上述严格边界的 `semantic_prompt_chars`（最终 user prompt，包含实际 examples、不含 system prompt；总数/均值/分位数和 A/B 降幅）；模型 API 返回的 prompt tokens 同时报告原始计数，但若当前 provider 无法按语义阶段归因，则标注为方向性，不用整条链路 total tokens 冒充召回阶段节省。

embedding 不参与上述三层，因此当前额度不足不影响验收。

## Risks / Trade-offs

- **[词面召回不理解真正语义]** → 无可靠信号回退完整 catalog；后续 C4 可在相同接口下增加 embedding/reranker，但不得改变本轮评测口径。
- **[alias 错配导致高置信漏召回]** → alias 变更必须带 golden 覆盖；Top-K 填充保留多个相近候选；离线 golden Recall@K 是合并门禁。
- **[在 49 条 judged cases 上标定过拟合]** → 报告明确 Recall 分母=49 的小样本；增加未进入阈值调优的对抗/低信号单测，不宣称生产泛化率。N=61 只用于端到端 A/B。
- **[full fallback 让 effective recall 虚高]** → strict/effective/fallback 三个口径分开，逐例列出 fallback 原因。
- **[运行时迁移 alias 路径破坏记忆校验或丢失评测元数据]** → `AliasBundle` 同时提供 `alias_map` 与 `alias_records`，增加旧别名数量、covered_by、最长匹配和 memory consistency 回归测试。
- **[真实 LLM A/B 受随机性和额度影响]** → 离线门禁作为硬证据；真实 A/B记录配置、原始分母和 ERROR，额度不足时允许暂停，不用 mock 数字替代真实结果。

## Migration Plan

1. 将别名资源迁到运行时目录并让现有 memory/eval consumer 通过统一 loader 读取，先跑旧测试保证行为不变。
2. 实现召回器、离线评测和阈值扫描，达到 golden effective recall 100% 且 topk 用例零漏召回后固化配置。
3. 接入 `semantic_resolve_node` 的 normal/inject 路径，保留 `METRIC_RECALL_MODE=full` 回滚开关。
4. 透传 debug 字段，运行 Python/Java 契约测试与 N=61 A/B；结果写入评测报告、开发日志和面试素材库。
5. 若出现可归因回退，切换 `METRIC_RECALL_MODE=full` 即恢复旧行为，无数据迁移。

## Open Questions

- Top-K 最终取 5 还是更大：由 49 条 judged cases 离线扫描决定，不能把全部 N=61 当作 Recall 分母或在 propose 阶段凭经验宣称。
- 词面阈值最终值：从 0.55 起扫描；若靠降低阈值导致大量弱候选，不如保留 full fallback。
- 后续是否把 aliases 并入企业式指标 catalog/API：本轮只调整本地依赖方向，留作 catalog governance change。
