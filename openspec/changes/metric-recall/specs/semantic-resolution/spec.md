## ADDED Requirements

### Requirement: 语义解析消费指标候选集
`SEMANTIC_RESOLVE` SHALL 从完整 catalog 生成指标候选，并仅将候选 catalog 提供给语义 LLM；安全回退时 SHALL 提供完整 catalog。记忆一致性与失效校验 SHALL 继续使用完整 catalog，近命中 inject 路径 SHALL 与普通解析路径消费同一候选 catalog。

#### Scenario: 普通解析使用候选 catalog
- **WHEN** 指标召回返回 `mode=topk`
- **THEN** `SemanticResolver` Prompt 中只包含候选指标，维度清单保持完整

#### Scenario: 记忆注入使用候选 catalog
- **WHEN** 语义记忆处于 inject 波段并需要调用 LLM
- **THEN** few-shot 示例与本次指标候选共同进入 Prompt，不重新注入完整 catalog

#### Scenario: 记忆命中校验不被裁剪
- **WHEN** 语义记忆处于 hit 波段并校验存储 intent 的 metric codes
- **THEN** 一致性和指标失效校验使用完整 catalog，不因候选裁剪接受失效指标或拒绝有效存储指标

#### Scenario: 召回回退保持旧路径
- **WHEN** 指标召回返回 `mode=full_fallback`
- **THEN** `SemanticResolver` 收到完整 catalog，后续 ResolvedIntent 与 SQL 合成流程不变

#### Scenario: 显式完整目录基线
- **WHEN** 指标召回配置为 `mode=full`
- **THEN** `SemanticResolver` 收到完整 catalog，且该次运行不标记为 fallback
