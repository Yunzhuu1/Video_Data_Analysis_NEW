## ADDED Requirements

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: golden 覆盖度
- **WHEN** 评测数据集（golden cases）包含多指标组合、多条件过滤、排名+时间嵌套、跨表 JOIN、长尾/歧义等场景
- **THEN** 每个可判定用例标注 `golden_spec`，可参与口径正确率统计；歧义题可不标 golden_spec（仅端到端统计）

#### Scenario: 难层客观筛选
- **WHEN** 对同义集 hard 层候选运行无记忆基线（组 A）
- **THEN** 仅保留实测 L1 失败的条目为"真难层"；hard 层若组 A 仍 100%，报告如实标注"该难度层注入无增益"，不硬凑

## MODIFIED Requirements

### Requirement: 量化指标测量
评测 SHALL 支持量化指标的测量与报告：token 计量（LLM 调用 usage）、同义表达问题集的注入收益/冷热启动实验、以及可写进简历的指标报告（含历史轨迹与对比基线）。同义集实验的 band 分层 SHALL 取自**与线上同一实现**的检索器（混合检索），报告 SHALL 注明**检索器实现/阈值/embedding 模型**三变量配置，并按**难度分层**（easy/hard）输出注入收益。

#### Scenario: token 计量
- **WHEN** 运行 real 模式评测
- **THEN** 每用例记录 LLM token 消耗（prompt/completion/total）；命中直通仅消除解析阶段 token（用例总 token 仍含回答阶段），报告以"命中 vs 未命中用例总 token 差"衡量

#### Scenario: 同义集注入收益（按波段分层，band 运行时取自检索器）
- **WHEN** 以同义表达问题集（YAML 存 question/golden/source_case/difficulty，不静态标 band）运行无记忆（--memory off）与有记忆（--memory on，先沉淀后同义集）两组，band 由 runner 对每条同义问题执行**与线上同一实现**的检索（取 top-1）
- **THEN** 报告对比 **inject 波段子集**的 L1 口径成功率与 inject 命中率；miss 波段子集单独报告（LLM 自身泛化）；hit 波段归直通实验；报告注明**检索器实现/阈值/embedding 模型**三变量（如 `hybrid(doubao-embedding-vision-251215)/0.92-0.80/w=0.7`）

#### Scenario: 难层注入收益（按难度分层）
- **WHEN** 同义集包含 `difficulty: hard` 条目，且已通过组 A 实测筛选（保留 L1<100% 的真难层）
- **THEN** 报告分别输出 easy/hard 两层的 N、组 A L1、组 B L1 与注入增益；hard 层增益 >0 说明注入示例将错误改写掰回正确，=0 则如实报告"该难度层注入无增益"

#### Scenario: 冷热启动（检索侧）
- **WHEN** 以空记忆（冷）与预置记忆 seed（热）分别运行同义集
- **THEN** 报告对比成功率与延迟（实验仅测检索侧，消除写路径方差，区别于全链路注入实验）

#### Scenario: 阈值标定可复现
- **WHEN** 生成混合检索的阈值标定报告
- **THEN** 输出同义集/毒化对/近重复对三组相似度分布，标注 hit 阈值（毒化对全部落于其下的最小值）与 inject 阈值（期望注入条目全部落于区间内的最大值），阈值可复现

#### Scenario: 指标报告
- **WHEN** 生成 `docs/metrics-report.md`
- **THEN** 包含历史轨迹表（逐轮端到端/L1/拦截率/命中率，附 commit）、正确性/安全/效率/记忆价值指标、实验协议与可复现说明，以及样本量 N 与难度分层
