## MODIFIED Requirements

### Requirement: 真实指标报告与基线对比
评测 SHALL 输出真实数字报告（`docs/eval-report.md`），并支持两个配置的 A/B 对比（逐指标 diff）。

#### Scenario: 报告含结果正确率
- **WHEN** 运行 real 平台评测
- **THEN** 报告包含 R1（结果正确率，可断言用例口径）与 L1-L4 并列，并含 `L1 对 + R1 错` 交叉诊断清单
