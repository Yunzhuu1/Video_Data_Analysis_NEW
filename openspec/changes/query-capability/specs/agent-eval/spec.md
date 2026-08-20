## MODIFIED Requirements

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: 数值过滤用例
- **WHEN** 合成器支持指标值过滤（HAVING）
- **THEN** 评测数据集含数值过滤用例（如"完播率超过50%的创作者"，aggregate/trend），n02 跨源多指标用例预期从 fallback 改为 semantic，R1 真值独立重取
