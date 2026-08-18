## MODIFIED Requirements

### Requirement: 记忆行为评测
评测 SHALL 隔离记忆对回归的影响：回归评测默认 `--memory off`；记忆行为（重复问题对、相似反例、命中率）由 `--memory on` 专用用例覆盖，且 `--memory on` 使用独立记忆库（跑完即弃）。命中率报告 SHALL 区分**场内自命中**（eval 协议）与**真实路径命中**（real-session 协议），不得混用口径。

#### Scenario: 命中率口径分离
- **WHEN** 生成评测报告
- **THEN** `memory_hit_rate` 标注为场内自命中口径（eval 协议）；真实路径命中率使用 `real_` 前缀指标（real-session 协议），两者并列展示且各自注明来源
