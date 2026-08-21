## ADDED Requirements

### Requirement: 指标候选召回评测
评测 SHALL 使用 `golden_spec.metrics` 独立测量指标候选召回，不调用 LLM、embedding 或数据库；报告 SHALL 分离 strict Recall@K、含完整目录回退的 effective recall、多指标完整召回率和 fallback 率，并展示原始分子/分母与逐例失败明细。

#### Scenario: golden metrics 召回门禁
- **WHEN** 对所有具有 `golden_spec.metrics` 的用例运行离线指标召回评测
- **THEN** effective recall 为 100%，且所有 `mode=topk` 用例的候选包含其全部 golden metrics；否则评测失败并列出用例、golden 与实际候选

#### Scenario: 多指标完整召回
- **WHEN** golden 用例包含两个或以上指标
- **THEN** 报告单列“全部 golden metrics 均被召回”的用例数/总数，不以命中任意一个指标代替完整召回

#### Scenario: 回退口径分离
- **WHEN** 某用例因低信号或异常使用完整 catalog
- **THEN** 该用例计入 effective recall，但不计作 strict Top-K 成功；报告按原因展示 fallback 原始计数

### Requirement: 完整目录与候选目录 A/B
评测 SHALL 支持在相同用例、LLM、平台、记忆和模型配置下对比 `metric_recall_mode=full` 与 `topk`。A/B SHALL 单独报告全量 N=61 与既有 N=57 子集的 L1-L4、ERROR、sql_source、Prompt 字符数和召回回退；真实 LLM 单轮结果 SHALL 标注为方向性观测，不把随机波动直接归因为召回收益或回退。

#### Scenario: 无 embedding 的真实 A/B
- **WHEN** 以 `--llm real --platform mock --memory off` 对比 full 与 topk，且 embedding 不可用
- **THEN** 两组均不调用 embedding，报告记录模型、用例数、Recall@K、L1-L4 原始计数和 ERROR 明细

#### Scenario: 既有子集回归口径
- **WHEN** N=61 全量 A/B 完成
- **THEN** 报告分别展示既有 N=57 子集和新增用例整体，禁止用新增用例改变分布后的整体数字代替既有子集回归结论

#### Scenario: Prompt 缩减口径
- **WHEN** 对比 full 与 topk 的语义输入规模
- **THEN** 以语义 Prompt 字符数的总量/均值/分位数作为确定性主指标，并报告 provider prompt token 原始计数（若不能按语义阶段归因则标注方向性），不得用整条链路 total tokens 冒充召回阶段节省

