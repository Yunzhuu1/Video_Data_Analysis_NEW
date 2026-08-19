## MODIFIED Requirements

### Requirement: 结果级断言（按 intent 分层）
评测 SHALL 对可确定结果的用例执行最终结果断言：aggregate 用精确值+容差，trend 用方向/模式断言，ranking 用集合+顺序断言；detail/歧义用例不断言。断言基于真实执行结果（real 平台），且 expected_result 取自确定性种子数据（seed 42）保证可复现。

#### Scenario: relative 时间用例纳入 R1
- **WHEN** relative 时间语义修复后运行 R1 评测
- **THEN** relative 可断言子集（aggregate/trend 用例，如 c03 最近7天）纳入断言范围，合成 SQL 含时间过滤且结果与 seed 42 真值一致（R1 扩展到 relative 子集全绿）；detail/歧义 relative 用例仅验证 SQL 形态（R1=N/A 不变）
