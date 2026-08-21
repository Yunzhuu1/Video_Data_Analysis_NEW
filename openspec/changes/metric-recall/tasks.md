## 1. 别名与配置基座

- [ ] 1.1 将 `app/eval/aliases.yaml` 迁移为运行时唯一别名资源，实现 `AliasBundle(alias_map, alias_records)` 统一 loader（既有 `get_aliases()` 为 map 兼容投影），并以数量、covered_by、冲突校验、最长匹配和既有一致性测试证明迁移零行为回退
- [ ] 1.2 在 settings 增加 `METRIC_RECALL_MODE=topk|full`、Top-K 与词面阈值配置（含无 pydantic 的兼容分支），默认不依赖 embedding

## 2. 确定性候选召回

- [ ] 2.1 实现 `MetricCandidateRetriever` 与结果/候选模型：NFKC/lower/仅保留 isalnum code point（`_` 移除、空表达丢弃）、精确名称/metricCode/最长别名 pinned、集合 n-gram 覆盖分（单字符只算 unigram）、稳定排序、pinned 超 K 不截断
- [ ] 2.2 实现低信号/无效 catalog/异常的 `full_fallback` 与显式配置的 `full`，固定 mode=`topk|full|full_fallback`；仅 full_fallback 设置 fallback=true/计入 fallback rate，保留回退前 ranked_candidates 与实际 prompt catalog、reason、数量和 warning
- [ ] 2.3 增加召回器单测，覆盖单指标、多指标、重叠别名最长优先、pinned>K、稳定排序、中文长上下文、低信号回退、异常回退和 embedding 未配置零调用

## 3. 语义链路接入

- [ ] 3.1 在 `semantic_resolve_node` 中只召回一次：full catalog 继续用于记忆一致性/失效校验，候选 catalog 同时用于 normal 与 memory inject 的 `SemanticResolver` 调用
- [ ] 3.2 只构造一次最终 user prompt并记录 `semantic_prompt_chars=len(build_semantic_user_prompt(...))`（不含 system；inject 含实际 examples），将同一字符串发送给 LLM；未调用语义 LLM 时记 null 并排除均值，确保 memory hit、召回回退和 raw SQL 降级行为不变
- [ ] 3.3 增加节点/Prompt 回归测试，断言 Top-K 不泄漏完整指标、inject 与 normal 候选一致、hit 校验仍看完整 catalog、full 模式恢复旧 Prompt

## 4. Debug 契约与透传

- [ ] 4.1 扩展 `DataAgentState`、Agent `AnalyzeResponse`、Spring `EngineAnalyzeResponse` 与 `includeDebug=true` 映射，透传 metricCandidates/mode/fallback/reason/K/catalog counts/semanticPromptChars
- [ ] 4.2 增加 Python API 与 Java Controller/DTO 契约测试，验证 debug 开启可见、默认业务响应不受影响、分数和顺序可复现

## 5. 离线门禁与 A/B 评测

- [ ] 5.1 为 eval runner 增加独立 metric-recall 评测及 `--metric-recall full|topk` A/B 配置；strict Recall@K 固定以 49 条的回退前 ranked Top-K 为分母，effective recall 按实际 prompt catalog，另报多指标完整召回/fallback 原因和逐例候选
- [ ] 5.2 仅在 N=61 中含 `golden_spec.metrics` 的 49 条 judged cases 上扫描 K/阈值并固化配置（Recall 分母=49）：effective recall=100%，所有 topk 用例 golden metrics 零遗漏；其余 12 条不进入 Recall 分母
- [ ] 5.3 运行全量 Python 测试与相关 Java 测试，确认别名迁移、记忆校验、语义解析、API 契约和既有 SQL 合成无回退
- [ ] 5.4 在 embedding 关闭条件下运行 `--llm real --platform mock --memory off` 的 full/topk N=61 A/B，单列既有 N=57 子集，报告 L1-L4/ERROR/sql_source/fallback 和 Prompt chars；真实单轮结果标注方向性并逐例审计差异

## 6. 文档与收尾

- [ ] 6.1 将架构动机、算法/回退口径、Recall@K 与 A/B 原始计数、局限性整理进开发日志、metrics report 和面试素材库，不把 full fallback 或单轮 LLM 波动包装成召回收益
- [ ] 6.2 运行 `openspec validate metric-recall --strict`、确认全部任务勾选并提交实现（仅 commit，由用户 push/merge）
