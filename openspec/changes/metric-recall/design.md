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

将 `app/eval/aliases.yaml` 移至运行时资源目录（如 `app/resources/metric_aliases.yaml`），保留 `alias`、`metric_code` 和覆盖元数据。`memory.aliases`、新召回器、评测及校验脚本统一通过同一个 loader 读取；评测代码不得再成为运行时依赖。

指标候选表达集固定由以下字段组成：

1. `metricCode`；
2. `metricName`；
3. 该 code 对应的人工审核 alias。

`businessDefinition` 不进入词面表达集：其长文本包含大量共享业务词，容易把“播放”“用户”等泛词扩散到无关指标。catalog 仍是指标定义唯一来源，别名资源只是用户表达映射，不复制公式和血缘。

备选方案是在 `metric_catalog.json` 每项内直接增加 aliases；这更接近完整企业 catalog，但会要求 Java DTO/数据库/API 同步扩展。C3 先保持无数据库迁移，后续可把别名迁入指标管理服务。

### D2：固定为“精确/最长别名 + 字符 n-gram”确定性召回

新增纯函数式 `MetricCandidateRetriever`。输入是 `question + full_catalog + aliases`，输出 `MetricRecallResult`：

```text
candidates: [{metric_code, score, reasons, matched_expressions}]
mode: topk | full_fallback
fallback_reason: null | no_reliable_signal | invalid_catalog | retriever_error
top_k / lexical_threshold / full_catalog_count / prompt_catalog_count
```

处理顺序：

1. 规范化问题与表达：大小写归一、去空白和标点；
2. 对 metricCode、metricName 和 alias 做子串匹配；表达重叠时按“更长表达优先”，同长度按 metric code 稳定排序；所有显式命中的 metric code 都设为 pinned；
3. 对每个指标计算其所有表达中的最高词面分。单个表达 `e` 相对问题 `q` 的分数固定为字符覆盖与二元字符覆盖的加权值：`0.35 * unigram_coverage(e,q) + 0.65 * bigram_coverage(e,q)`；coverage 为表达 n-gram 在问题 n-gram 中的交集数除以表达 n-gram 数，因而不受问题附加时间/维度词长度稀释；
4. pinned 指标全部保留，再按 `(-score, metric_code)` 填充到 K。若 pinned 数量超过 K，返回全部 pinned，不截断真实多指标表达；
5. 没有 pinned 且最高词面分低于阈值时，不做强猜，回退完整 catalog。

默认候选 K 从 5 开始，词面阈值从 0.55 开始；apply 阶段通过 N=61 golden 离线扫描标定并写死最终值。若 K=5 不能达到 judged golden metrics Recall@K=100%，增大 K 或对失败类型增加经审核 alias，不能以降低召回门槛掩盖漏召回。报告必须记录最终 K、阈值、表达数据版本和原始计数。

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

`prompt_catalog = recall_result.candidates`；`mode=full_fallback` 时等于完整 catalog。这样候选裁剪不会削弱记忆命中的 catalog 一致性校验，也不会让已失效指标通过。召回异常只记录 warning 并回退完整 catalog，不允许打断主链路。

为支持 A/B，配置 `METRIC_RECALL_MODE=topk|full`：默认 `topk`，`full` 仅用于基线/紧急回滚。K 与阈值也进入 settings；线上无需修改请求协议。

### D4：回退是正确性边界，不是“召回失败”粉饰

以下情况必须使用完整 catalog：

- catalog 为空/条目缺少 code，召回器无法构建有效索引；
- 无显式命中且最高词面分低于标定阈值；
- loader、别名校验或召回计算抛异常；
- 配置显式指定 `mode=full`。

回退用例仍可正常由 LLM 解析，但单独计入 `metric_recall_fallback_rate`。不能把 full fallback 计作 Top-K 命中来夸大裁剪覆盖；离线指标同时报告：

- `strict_recall@K`：仅 `mode=topk` 的候选是否包含全部 golden metrics；
- `effective_recall`：包含 full fallback 后是否可见全部 golden metrics；
- fallback 原始计数和原因分布。

验收硬门槛为 effective recall 100%，且任何 topk 用例不得漏 golden metric；若某用例只能靠 full fallback 保真，要如实报告为“未裁剪覆盖”。

### D5：观测字段走既有 debug 通道

`DataAgentState` 增加 `metric_candidates`、`metric_recall_mode`、`metric_recall_fallback`、`metric_recall_reason`、`metric_recall_top_k`、`semantic_prompt_chars`。Agent `/analyze` 响应和 Spring `includeDebug=true` 增量透传 camelCase 字段；默认业务响应不展示这些数据。

候选只记录 code、分数和原因，不记录用户问题之外的新敏感数据。分数保留固定小数位，候选顺序稳定，便于测试和面试演示。

### D6：评测先证明“没漏”，再观察“是否更好”

评测分三层：

1. **离线确定性门禁**：对所有含 `golden_spec.metrics` 的用例直接调用召回器，输出 Recall@K、effective recall、多指标完整召回率、fallback 率和逐例候选；不调用 LLM、embedding 或数据库。
2. **单元/回放回归**：验证最长匹配、稳定排序、pinned>K、低信号回退、异常回退、记忆 inject 使用候选 catalog，以及 debug 透传。
3. **真实 LLM A/B**：同一 N=61、`--platform mock --memory off`，A=`mode=full`，B=`mode=topk`。分别报告整体 N=61 和既有 N=57 子集的 L1-L4、sql_source、ERROR、fallback 原始计数。模型单轮存在随机性，真实 A/B 只作方向性观测；若 B 下降，必须逐例核查是否与漏召回相关，必要时复跑，不把单轮波动直接归因于召回。

Prompt 缩减的主指标使用确定性的 `semantic_prompt_chars`（总数/均值/分位数和 A/B 降幅）；模型 API 返回的 prompt tokens 同时报告原始计数，但若当前 provider 无法按语义阶段归因，则标注为方向性，不用整条链路 total tokens 冒充召回阶段节省。

embedding 不参与上述三层，因此当前额度不足不影响验收。

## Risks / Trade-offs

- **[词面召回不理解真正语义]** → 无可靠信号回退完整 catalog；后续 C4 可在相同接口下增加 embedding/reranker，但不得改变本轮评测口径。
- **[alias 错配导致高置信漏召回]** → alias 变更必须带 golden 覆盖；Top-K 填充保留多个相近候选；离线 golden Recall@K 是合并门禁。
- **[在 N=61 上标定过拟合]** → 报告明确小样本；增加未进入阈值调优的对抗/低信号单测，不宣称生产泛化率。
- **[full fallback 让 effective recall 虚高]** → strict/effective/fallback 三个口径分开，逐例列出 fallback 原因。
- **[运行时迁移 alias 路径破坏记忆校验]** → loader 保持同一返回契约，增加旧别名数量、最长匹配和 memory consistency 回归测试。
- **[真实 LLM A/B 受随机性和额度影响]** → 离线门禁作为硬证据；真实 A/B记录配置、原始分母和 ERROR，额度不足时允许暂停，不用 mock 数字替代真实结果。

## Migration Plan

1. 将别名资源迁到运行时目录并让现有 memory/eval consumer 通过统一 loader 读取，先跑旧测试保证行为不变。
2. 实现召回器、离线评测和阈值扫描，达到 golden effective recall 100% 且 topk 用例零漏召回后固化配置。
3. 接入 `semantic_resolve_node` 的 normal/inject 路径，保留 `METRIC_RECALL_MODE=full` 回滚开关。
4. 透传 debug 字段，运行 Python/Java 契约测试与 N=61 A/B；结果写入评测报告、开发日志和面试素材库。
5. 若出现可归因回退，切换 `METRIC_RECALL_MODE=full` 即恢复旧行为，无数据迁移。

## Open Questions

- Top-K 最终取 5 还是更大：由 N=61 离线扫描决定，不能在 propose 阶段凭经验宣称。
- 词面阈值最终值：从 0.55 起扫描；若靠降低阈值导致大量弱候选，不如保留 full fallback。
- 后续是否把 aliases 并入企业式指标 catalog/API：本轮只调整本地依赖方向，留作 catalog governance change。
