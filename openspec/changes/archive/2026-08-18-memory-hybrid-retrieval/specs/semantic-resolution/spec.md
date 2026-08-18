## MODIFIED Requirements

### Requirement: 语义记忆检索与写入
`SEMANTIC_RESOLVE` SHALL 在调用 LLM 前先检索语义记忆：命中（高相似）直接复用历史 ResolvedIntent（含 metrics 一致性校验），近命中注入 few-shot 示例，未命中走 LLM；记忆写入 SHALL 仅发生在全链路成功之后，且记忆不直接进入 SQL。检索 SHALL 采用**语义 + 词面多信号融合**（embedding 语义 cosine 为主、BM25 词面为辅），并保留**精确匹配快路径**；embedding 模型不可用 SHALL 降级为文本相似度检索（行为不劣于现状）。

#### Scenario: 精确匹配快路径
- **WHEN** 规范化问题与记忆库某条目 `norm_question` 完全相等
- **THEN** 直接判为命中（score=1.0，不依赖 embedding 模型），复用存储的 ResolvedIntent，`sql_source=memory`

#### Scenario: 记忆命中直通
- **WHEN** 规范化问题与记忆库条目**多信号融合相似度** ≥ 阈值且 catalog 校验通过且 **metrics 一致性校验通过**（问题文本匹配到的指标名与存储 metric_codes 一致）
- **THEN** `SEMANTIC_RESOLVE` 不调用 LLM，直接复用存储的 ResolvedIntent，`sql_source=memory`

#### Scenario: 相似但不同指标不误命中
- **WHEN** 问题文本匹配到某指标名但存储条目的 metric_codes 不一致（如"最近7天点赞量" vs 存储的"播放量"）
- **THEN** 不直通复用，降级为近命中注入或未命中

#### Scenario: 近命中注入示例
- **WHEN** 多信号融合相似度处于注入区间
- **THEN** 历史 (question→intent) 示例注入语义 prompt（≤3 条），LLM 照常解析

#### Scenario: embedding 不可用降级
- **WHEN** embedding 模型加载/推理失败（网络、依赖、模型缺失）
- **THEN** 检索降级为文本相似度（difflib）双阈值，主链路不受影响

#### Scenario: 记忆写入条件
- **WHEN** 一次语义路径 run 全链路成功（执行成功 + DQ 通过/警告）
- **THEN** 该 run 的规范化问题与 ResolvedIntent 写入记忆库（upsert）；失败 run 不写入

#### Scenario: 记忆失效
- **WHEN** 记忆条目引用的指标不在当前 catalog（口径变更）、解析规则哈希已变化、或 embedding 模型版本已变化
- **THEN** 该条目不参与命中（口径变更条目删除；embedding 模型变更条目重算）
