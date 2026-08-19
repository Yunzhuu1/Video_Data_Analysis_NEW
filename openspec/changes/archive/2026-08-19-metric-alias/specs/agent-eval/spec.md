## MODIFIED Requirements

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: 指标表达覆盖
- **WHEN** 指标表达映射（别名/指纹）新增条目
- **THEN** 评测数据集含对应覆盖用例（至少 1 个 golden/同义用例），且真实评测报告别名匹配命中情况（alias_hit）
