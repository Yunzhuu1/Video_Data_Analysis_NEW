## 1. 别名与配置基座

- [ ] 1.1 将 `app/eval/aliases.yaml` 迁移为运行时唯一别名资源，更新 memory/eval consumer 的统一 loader，并以数量、最长匹配和既有一致性测试证明迁移零行为回退
- [ ] 1.2 在 settings 增加 `METRIC_RECALL_MODE=topk|full`、Top-K 与词面阈值配置（含无 pydantic 的兼容分支），默认不依赖 embedding

## 2. 确定性候选召回

- [ ] 2.1 实现 `MetricCandidateRetriever` 与结果/候选模型：规范化、精确名称/metricCode/最长别名 pinned、0.35 unigram + 0.65 bigram 覆盖分、稳定排序、pinned 超 K 不截断
- [ ] 2.2 实现低信号/无效 catalog/异常/full 配置的完整 catalog 回退，保留明确 mode、reason、catalog 数量和 warning
- [ ] 2.3 增加召回器单测，覆盖单指标、多指标、重叠别名最长优先、pinned>K、稳定排序、中文长上下文、低信号回退、异常回退和 embedding 未配置零调用

## 3. 语义链路接入

- [ ] 3.1 在 `semantic_resolve_node` 中只召回一次：full catalog 继续用于记忆一致性/失效校验，候选 catalog 同时用于 normal 与 memory inject 的 `SemanticResolver` 调用
- [ ] 3.2 记录本次语义 Prompt 字符数及候选元数据；确保 memory hit 直通、召回失败回退和 raw SQL 降级路径行为不变
- [ ] 3.3 增加节点/Prompt 回归测试，断言 Top-K 不泄漏完整指标、inject 与 normal 候选一致、hit 校验仍看完整 catalog、full 模式恢复旧 Prompt

## 4. Debug 契约与透传

- [ ] 4.1 扩展 `DataAgentState`、Agent `AnalyzeResponse`、Spring `EngineAnalyzeResponse` 与 `includeDebug=true` 映射，透传 metricCandidates/mode/fallback/reason/K/catalog counts/semanticPromptChars
- [ ] 4.2 增加 Python API 与 Java Controller/DTO 契约测试，验证 debug 开启可见、默认业务响应不受影响、分数和顺序可复现

## 5. 离线门禁与 A/B 评测

- [ ] 5.1 为 eval runner 增加独立 metric-recall 评测及 `--metric-recall full|topk` A/B 配置，报告 strict Recall@K/effective recall/多指标完整召回/fallback 原因和逐例候选（均带原始分子分母）
- [ ] 5.2 在 N=61 golden 上扫描 K/阈值并固化配置：effective recall=100%，所有 topk 用例 golden metrics 零遗漏；若 K=5 不满足则增大 K 或补经审核 alias，不降低正确性门槛
- [ ] 5.3 运行全量 Python 测试与相关 Java 测试，确认别名迁移、记忆校验、语义解析、API 契约和既有 SQL 合成无回退
- [ ] 5.4 在 embedding 关闭条件下运行 `--llm real --platform mock --memory off` 的 full/topk N=61 A/B，单列既有 N=57 子集，报告 L1-L4/ERROR/sql_source/fallback 和 Prompt chars；真实单轮结果标注方向性并逐例审计差异

## 6. 文档与收尾

- [ ] 6.1 将架构动机、算法/回退口径、Recall@K 与 A/B 原始计数、局限性整理进开发日志、metrics report 和面试素材库，不把 full fallback 或单轮 LLM 波动包装成召回收益
- [ ] 6.2 运行 `openspec validate metric-recall --strict`、确认全部任务勾选并提交实现（仅 commit，由用户 push/merge）
