## MODIFIED Requirements

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: 评测数据规模扩展
- **WHEN** 数据模型规模化（新表/新指标）落地
- **THEN** golden cases 从 N=45 扩展至 ~70，覆盖新指标（比率/收益/去重）、新表跨表关系、真实分布查询；新用例含 golden_spec 与 R1 expected_result（独立手工 SQL 取 seed 42 真值）
