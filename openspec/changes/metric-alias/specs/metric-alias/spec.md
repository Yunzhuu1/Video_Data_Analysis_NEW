## ADDED Requirements

### Requirement: 指标表达映射
系统 SHALL 提供"自然语言表达 → 指标 ID"的确定性映射：静态别名表（`aliases.yaml`，人工审核沉淀）与可选的自学习表达指纹（从写路径沉淀按 metric_codes 归属派生）。读取侧指标匹配 SHALL 在 catalog 精确名之外按表达映射扩展，且不削弱 metrics 一致性双保险（stored metric_codes 必须与判定结果一致才直通）。

#### Scenario: 别名匹配
- **WHEN** 问题文本包含别名表条目（如「播放走势」→ total_plays）
- **THEN** `extract_metric_names` 将对应 metric ID 纳入判定集合，且 catalog 精确名优先级高于别名

#### Scenario: 双保险保留
- **WHEN** 问题文本匹配到的指标 ID 与记忆条目 metric_codes 不一致（如「点赞量」vs 存储 total_plays）
- **THEN** 直通被拦截（metrics_consistent=False），行为不因别名引入而改变

#### Scenario: 别名覆盖验证
- **WHEN** 别名表新增条目
- **THEN** 至少 1 个 golden/同义用例覆盖该别名（防别名失效），别名不覆盖已存在的 catalog 精确名

### Requirement: 虚拟澄清实验
评测 SHALL 支持虚拟澄清实验：定义"歧义判定"（低置信/多指标候选），用 golden 自动模拟用户选择，产出潜在澄清率、虚拟澄清收益（澄清后 L1 差）、澄清率随记忆沉淀的下降曲线——用于验证 HITL 指标澄清叙事的数字，不实现真 HITL 交互。

#### Scenario: 潜在澄清率
- **WHEN** 以无记忆基线运行虚拟澄清实验
- **THEN** 输出歧义问题占比（潜在澄清率）与澄清后 L1 vs 不澄清 L1 的差值（虚拟澄清收益）

#### Scenario: 澄清率随记忆下降
- **WHEN** 沉淀后再跑同义集并统计歧义问题数
- **THEN** 输出澄清率变化（记忆能否自动化掉澄清），报告注明"虚拟澄清=golden 模拟完美用户，数字为上限参考"
