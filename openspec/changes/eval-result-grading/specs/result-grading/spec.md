## ADDED Requirements

### Requirement: 结果级断言（按 intent 分层）
评测 SHALL 对可确定结果的用例执行最终结果断言：aggregate 用精确值+容差，trend 用方向/模式断言，ranking 用集合+顺序断言；detail/歧义用例不断言。断言基于真实执行结果（real 平台），且 expected_result 取自确定性种子数据（seed 42）保证可复现。

#### Scenario: aggregate 精确值断言
- **WHEN** 用例 intent=aggregate 且标注 `expected_result: {type: "exact", value, tolerance}`
- **THEN** 真实执行结果数值与 value 之差 ≤ tolerance 判通过，否则 R1 失败

#### Scenario: trend 方向断言
- **WHEN** 用例 intent=trend 且标注 `expected_result: {type: "trend_pattern", points}`
- **THEN** 关键点方向/激增下降模式与断言匹配判通过（不逐点比精确值）

#### Scenario: ranking 集合+顺序断言
- **WHEN** 用例 intent=ranking 且标注 `expected_result: {type: "top_set", items, ordered?}`
- **THEN** top 集合命中（必选）与顺序（可选）判通过

### Requirement: R1 维度与交叉诊断
评测报告 SHALL 输出结果正确率 R1（结果断言通过数/可断言用例数），与 L1-L4 并列且端到端口径不变；L1 错 → R1 标记 N/A（不可判定，非失败）；`L1 对 + R1 错` 用例 SHALL 单列（解析对但 SQL 错的合成器/生成 bug 信号）。

#### Scenario: R1 独立报告
- **WHEN** 生成评测报告
- **THEN** 包含 R1（结果正确率）与 L1-L4 并列展示，且端到端（L1 口径）数值不受 R1 影响

#### Scenario: L1 错 R1 不判
- **WHEN** 用例 L1 未通过
- **THEN** R1 标记 N/A（不因"结果碰巧对"产生假阳性）

#### Scenario: 交叉诊断
- **WHEN** 存在 L1 对且 R1 错的用例
- **THEN** 报告单列该清单并标注"解析对但 SQL 错（合成器/SQL 生成 bug 信号）"

### Requirement: 平台行为
结果级断言 SHALL 仅在 real 平台（真实 MySQL 执行）生效；mock/replay 平台结果断言标记 N/A（mock 执行返回写死假数据，与 SQL 无关，断言无意义）。

#### Scenario: mock 平台 R1 N/A
- **WHEN** 以 --platform mock 运行评测
- **THEN** 结果断言不执行，R1=N/A，L1-L4 行为不变
