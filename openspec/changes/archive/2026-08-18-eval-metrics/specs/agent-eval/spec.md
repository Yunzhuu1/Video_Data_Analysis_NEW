## ADDED Requirements

### Requirement: 量化指标测量
评测 SHALL 支持量化指标的测量与报告：token 计量（LLM 调用 usage）、同义表达问题集的注入收益/冷热启动实验、以及可写进简历的指标报告（含历史轨迹与对比基线）。

#### Scenario: token 计量
- **WHEN** 运行 real 模式评测
- **THEN** 每用例记录 LLM token 消耗（prompt/completion/total）；命中直通仅消除解析阶段 token（用例总 token 仍含回答阶段），报告以"命中 vs 未命中用例总 token 差"衡量

#### Scenario: 同义集注入收益（按波段分层，band 运行时取自检索器）
- **WHEN** 以同义表达问题集（YAML 存 question/golden/source_case，不静态标 band）运行无记忆（--memory off）与有记忆（--memory on，先沉淀后同义集）两组，band 由 runner 对每条同义问题执行真实检索取 top-1
- **THEN** 报告对比 **inject 波段子集**的 L1 口径成功率与 inject 命中率；miss 波段子集单独报告（LLM 自身泛化）；hit 波段归直通实验；报告注明检索器/阈值/embedding 模型三变量

#### Scenario: 冷热启动（检索侧）
- **WHEN** 以空记忆（冷）与预置记忆 seed（热）分别运行同义集
- **THEN** 报告对比成功率与延迟（实验仅测检索侧，消除写路径方差，区别于全链路注入实验）

#### Scenario: 指标报告
- **WHEN** 生成 `docs/metrics-report.md`
- **THEN** 包含历史轨迹表（逐轮端到端/L1/拦截率/命中率，附 commit）、正确性/安全/效率/记忆价值指标、实验协议与可复现说明
