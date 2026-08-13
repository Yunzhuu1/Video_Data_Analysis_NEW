## ADDED Requirements

### Requirement: 真实模式观测完整性
真实模式评测（platform=real）SHALL 观测等待审批状态、语义解析结果与 SQL 来源，使报告如实反映系统行为，且不得因等待审批路径丢失观测数据。

#### Scenario: 等待审批状态可见
- **WHEN** 引擎对某用例返回 WAITING_APPROVAL
- **THEN** 该用例评测结果记录 status=WAITING_APPROVAL，且与平台运行记录（agent_run）一致

#### Scenario: 等待审批用例的语义结果可见
- **WHEN** 用例触发等待审批且语义解析成功
- **THEN** 评测仍能取得该用例的 resolvedIntent 并参与口径正确率统计，而非按未解析计 0 分

#### Scenario: 报告含 SQL 来源
- **WHEN** 运行真实模式评测
- **THEN** 报告 Source 列展示语义合成或降级来源（semantic/fallback），而非恒为 "-"
