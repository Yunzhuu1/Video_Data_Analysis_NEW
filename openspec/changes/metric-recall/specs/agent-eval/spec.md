## ADDED Requirements

### Requirement: 指标候选召回评测
评测 SHALL 仅使用 N=61 中含 `golden_spec.metrics` 的 49 条 judged cases 独立测量指标候选召回（两个 recall 分母均为 49），其余 12 条不得进入 recall 分母；该评测不调用 LLM、embedding 或数据库。报告 SHALL 同时提供传统 `recall@configured_k`（检查 `ranked_candidates[:configured_k]`）与 pinned-aware `strict_recall@effective_k`（检查 `ranked_candidates[:max(configured_k,pinned_count)]`）；前者为可比诊断指标，后者为正确性门禁。full fallback 不得因最终看到完整目录而自动提高上述指标；effective recall SHALL 检查实际 Prompt catalog。报告 SHALL 明示 configured_k、pinned_expansion_count、逐例 effective_k、多指标完整召回率和 fallback 率，并展示原始分子/分母与逐例失败明细；显式 `mode=full` 不计入 fallback rate。

#### Scenario: golden metrics 召回门禁
- **WHEN** 对所有具有 `golden_spec.metrics` 的用例运行离线指标召回评测
- **THEN** `strict_recall@effective_k` 与 effective recall 均为 49/49；`recall@configured_k` 同时报告真实分子/49但不因预期 pinned 扩容单独阻塞；失败明细列出用例、golden、configured/effective candidates

#### Scenario: 多指标完整召回
- **WHEN** golden 用例包含两个或以上指标
- **THEN** 报告单列“全部 golden metrics 均被召回”的用例数/总数，不以命中任意一个指标代替完整召回

#### Scenario: pinned 超过配置 K 的双 recall
- **WHEN** 某 judged case 显式命中的 pinned 指标数大于 configured K
- **THEN** `recall@configured_k` 按固定 K 如实计算，`strict_recall@effective_k` 使用 `effective_k=pinned_count` 检查全部 pinned 候选，并增加 pinned_expansion_count，禁止混用两个指标名称

#### Scenario: 回退口径分离
- **WHEN** 某用例因低信号或异常使用完整 catalog
- **THEN** effective recall 按最终完整 Prompt catalog 判定；两个 ranked recall 仍分别按回退前 configured/effective candidates 判定，不能因回退自动成功；报告按原因展示 fallback 原始计数

#### Scenario: 无 golden 用例不进入召回分母
- **WHEN** 全量 N=61 中存在 12 条未配置 `golden_spec.metrics` 的用例
- **THEN** 这些用例只参与端到端 A/B，`recall@configured_k` 与 `strict_recall@effective_k` 分母均保持 49

### Requirement: 完整目录与候选目录 A/B
评测 SHALL 支持在相同用例、LLM、平台、记忆和模型配置下对比 `metric_recall_mode=full` 与 `topk`。A/B SHALL 单独报告全量 N=61 与既有 N=57 子集的 L1-L4、ERROR、sql_source、Prompt 字符数和召回回退；真实 LLM 单轮结果 SHALL 标注为方向性观测，不把随机波动直接归因为召回收益或回退。

#### Scenario: 无 embedding 的真实 A/B
- **WHEN** 以 `--llm real --platform mock --memory off` 对比 full 与 topk，且 embedding 不可用
- **THEN** 两组均不调用 embedding，报告记录模型、用例数、两种 recall、configured_k、pinned_expansion_count、L1-L4 原始计数和 ERROR 明细

#### Scenario: 既有子集回归口径
- **WHEN** N=61 全量 A/B 完成
- **THEN** 报告分别展示既有 N=57 子集和新增用例整体，禁止用新增用例改变分布后的整体数字代替既有子集回归结论

#### Scenario: Prompt 缩减口径
- **WHEN** 对比 full 与 topk 的语义输入规模
- **THEN** 两组均以实际发送的最终 user prompt `len(build_semantic_user_prompt(...))` 统计字符数（不含 system prompt；包含实际 inject examples；本轮 memory off 因而均无 examples），以总量/均值/分位数作为确定性主指标；provider prompt token 若不能按语义阶段归因则标注方向性，不得用整条链路 total tokens 冒充召回阶段节省
