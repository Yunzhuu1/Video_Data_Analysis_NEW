## ADDED Requirements

### Requirement: 记忆行为评测
评测 SHALL 隔离记忆对回归的影响：回归评测默认 `--memory off`；记忆行为（重复问题对、相似反例、命中率）由 `--memory on` 专用用例覆盖，且 `--memory on` 使用独立记忆库（跑完即弃）。

#### Scenario: 回归隔离
- **WHEN** 运行 golden cases 全量回归
- **THEN** 记忆默认关闭，解析结果不来自记忆（防止记忆掩盖解析回归）

#### Scenario: 重复问题同问同答
- **WHEN** 同一 question 在开启记忆下连续运行两次（两遍都成功解析）
- **THEN** 第二次 `memory_hit=true` 且 resolvedIntent 与第一次逐字段一致（一致率 100%）

#### Scenario: 相似反例不误命中
- **WHEN** 记忆库只有"最近7天播放量"，查询"最近7天点赞量"
- **THEN** 该查询不得命中（band != hit），避免静默错误指标

#### Scenario: 命中率可观测
- **WHEN** 评测报告生成
- **THEN** 包含 `memory_hit_rate` 与 `memory_inject_rate`，与 L1-L4 并列展示
