## ADDED Requirements

### Requirement: 多协议对抗评测调度
既有评测 runner SHALL 支持从独立 adversarial manifest 调度 question、fixed intent、mutated plan/snapshot 与 raw SQL/fault injection，并将各 adapter 的 observation 归一为统一的 disposition/stage/code/node trace/audit/result 结构；普通 N=61 runner 行为 SHALL 保持不变。

#### Scenario: 对抗协议统一执行
- **WHEN** 使用 adversarial CLI 运行指定 profile
- **THEN** runner 按 case protocol 调用对应 adapter，输出20条逐例 observation 和按层聚合，不将 adapter 异常静默吞为产品失败

#### Scenario: 普通评测零行为回退
- **WHEN** 使用既有参数运行 N=61 replay/mock 回归
- **THEN** 用例选择、L1-L4、R1、sql_source 和状态路由与引入 adversarial runner 前一致，对抗字段不改变既有分母

### Requirement: 对抗审计完整性比较器
评测比较器 SHALL 按 case layer 校验 required audit fields、must-visit/must-not-visit nodes、selected plan/catalog version/fallback reason/approval SQL hash 等相关证据，并将缺失字段与处置不符分开报告。

#### Scenario: 按层检查审计机会数
- **WHEN** 汇总 Semantic、Planning、Synthesis、Safety/Recovery observations
- **THEN** 每层仅以其 required audit fields 的实际机会数为分母，分别输出完整数/总数和缺失字段明细

#### Scenario: 处置错误与审计缺失分离
- **WHEN** 某 case 的 disposition 符合 expected 但缺少 required audit field
- **THEN** Expected Disposition 可通过但 Audit Completeness 失败，报告不得合并为一个模糊错误

