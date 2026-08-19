## MODIFIED Requirements

### Requirement: 评测数据覆盖与难度分层
评测数据集 SHALL 具备可扩展的覆盖度与难度分层：golden cases 覆盖多指标/多条件/跨表/长尾歧义等多类场景；同义表达集 SHALL 标注 `difficulty`（easy/hard），**hard 层以"无记忆基线（组 A）实测 L1<100%"为客观筛选标准**，不拍脑袋标难。

#### Scenario: 多指标用例语义路径验证
- **WHEN** 运行 --memory off 全量回归
- **THEN** 同源表多指标用例（如 n01 播放量+点赞量）sql_source=semantic 且 L1 正确；跨源表多指标用例（如 n02 完播率+互动率）保持 fallback 并在报告标注已知边界
