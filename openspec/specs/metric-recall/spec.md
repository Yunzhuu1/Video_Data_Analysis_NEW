# metric-recall Specification

## Purpose
TBD - created by archiving change metric-recall. Update Purpose after archive.
## Requirements
### Requirement: 确定性指标候选召回
系统 SHALL 在语义 LLM 调用前，根据完整指标 catalog 与经审核别名，以确定性的精确名称/最长别名匹配和字符 n-gram 词面分数生成稳定排序的指标候选。规范化 SHALL 固定为 Unicode NFKC、lower、仅保留 `isalnum` code point（包括移除 metric code 的 `_`）；空表达 SHALL 丢弃，单字符表达 SHALL 只计算 unigram coverage，不得产生 bigram 零分母。召回 SHALL 不依赖 embedding API；每例候选上限 SHALL 取 `effective_k=max(configured_top_k,pinned_count)`，显式命中的多指标 SHALL 全部保留，即使命中数超过配置 Top-K 也不得截断。

#### Scenario: 单指标候选召回
- **WHEN** 用户问题包含 catalog 指标名、metric code 或已审核别名
- **THEN** 对应 metric code 出现在候选中，结果记录分数、命中表达和命中原因

#### Scenario: 多指标显式命中全部保留
- **WHEN** 用户问题同时显式提及多个指标名称或别名，且显式命中数达到或超过 Top-K
- **THEN** `effectiveK=max(configuredK,pinnedCount)`，所有显式命中的 metric code 均进入候选，不因配置 Top-K 被截断

#### Scenario: 召回结果稳定
- **WHEN** 使用相同问题、catalog、别名版本、Top-K 与阈值重复召回
- **THEN** 候选 code、顺序、分数和原因完全一致

#### Scenario: 统一别名数据契约
- **WHEN** memory、指标召回或评测读取指标别名
- **THEN** 三者消费同一 `AliasBundle`；运行时使用 alias map，评测使用同源 alias records/covered_by，禁止评测自行解析另一份 YAML

#### Scenario: n-gram 边界输入
- **WHEN** 表达含下划线/标点、归一化后为空或仅含一个 Unicode code point
- **THEN** 下划线/标点按固定规则移除，空表达被忽略，单字符表达只计算 unigram 且不发生除零

#### Scenario: 无 embedding 运行
- **WHEN** embedding key、模型或额度不可用
- **THEN** 指标召回仍以纯本地词面算法完成，不发起 embedding 请求且不影响语义主链路

### Requirement: 指标召回安全回退
系统 SHALL 在无可靠词面信号、catalog/别名无效、召回异常或配置为 full 模式时，把完整 catalog 提供给语义解析器。回退 SHALL 标记原因，且不得以回退后的完整可见性冒充 Top-K 召回成功。

#### Scenario: 低信号回退完整 catalog
- **WHEN** 问题无显式指标命中且最高词面分低于标定阈值
- **THEN** `mode=full_fallback`，Prompt catalog 等于完整 catalog，并记录 `no_reliable_signal`

#### Scenario: 召回异常不打断主链路
- **WHEN** 别名加载或候选计算抛出异常
- **THEN** 系统记录 warning 并回退完整 catalog，仍继续语义解析

#### Scenario: 显式 full 回滚
- **WHEN** 配置 `METRIC_RECALL_MODE=full`
- **THEN** 系统跳过 Top-K 裁剪并使用完整 catalog，返回 `mode=full`、`fallback=false`、空 fallback reason，恢复 change 前行为且不计入 fallback rate

### Requirement: 指标召回运行时观测
系统 SHALL 在 state 和既有 debug 通道记录回退前候选 code/分数/原因、召回模式（`topk|full|full_fallback`）、回退状态与原因、configured K、pinned count、effective K、完整/Prompt catalog 数量和语义 Prompt 字符数。`semanticPromptChars` SHALL 等于实际发送给 LLM 的最终 `build_semantic_user_prompt(...)` user message 的 Python `len()`，不含 system prompt；memory inject 时包含实际 examples；未调用语义 LLM时为 null 且不进入均值。默认业务响应 SHALL 不展示该调试信息。

#### Scenario: Top-K 观测数据
- **WHEN** `includeDebug=true` 且本次使用 Top-K 候选调用语义解析器
- **THEN** debug 返回 `metricCandidates`、`metricRecallMode=topk`、`metricRecallFallback=false`、配置参数和 `semanticPromptChars`

#### Scenario: 回退观测数据
- **WHEN** 本次使用完整 catalog 回退
- **THEN** debug 返回 `metricRecallMode=full_fallback`、`metricRecallFallback=true` 和非空回退原因

