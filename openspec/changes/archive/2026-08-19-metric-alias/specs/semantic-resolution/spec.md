## MODIFIED Requirements

### Requirement: 语义记忆检索与写入
`SEMANTIC_RESOLVE` SHALL 在调用 LLM 前先检索语义记忆：命中（高相似）直接复用历史 ResolvedIntent（含 metrics 一致性校验），近命中注入 few-shot 示例，未命中走 LLM；记忆写入 SHALL 仅发生在全链路成功之后，且记忆不直接进入 SQL。检索 SHALL 采用**语义 + 词面多信号融合**（embedding 语义 cosine 为主、BM25 词面为辅），并保留**精确匹配快路径**；embedding 模型不可用 SHALL 降级为文本相似度检索（行为不劣于现状）。metrics 一致性校验 SHALL 支持**指标表达映射**（别名表/表达指纹）扩展匹配，不再仅依赖问题文本中的 catalog 指标名字符串包含。

#### Scenario: 表达映射下的一致性校验
- **WHEN** 命中条目的 metric_codes 与问题文本经表达映射（别名/指纹）判定出的指标 ID 一致
- **THEN** 一致性校验通过，可直通；映射判定为空时仍降级（不直通）
