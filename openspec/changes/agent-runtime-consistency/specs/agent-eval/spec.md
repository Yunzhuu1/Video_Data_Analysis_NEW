## ADDED Requirements

### Requirement: Agent 运行时一致性回归
评测 SHALL 将 catalog、memory、Run Trace 与相对时间的真实运行时契约作为独立确定性门槛，并将确定性根因消除与真实 LLM 单轮质量分开报告。修复前基线 SHALL 固定引用 commit/报告；修复后不得通过修改 golden、expected 或手工补库掩盖失败。

#### Scenario: Catalog 修复前后归因
- **WHEN** 在旧 7 指标数据库上完成 reconciliation 后重跑真实 Spring + Agent + MySQL N=61
- **THEN** 报告同时给出 API/Agent catalog code 覆盖、catalog-caused failures 原始计数、L1-L4 与 R1；硬门槛为受管 15 code 全覆盖、catalog-caused failures 13→0、既有 R1 21/21 不回退，不要求随机 LLM 单轮 L1 必须 49/49

#### Scenario: 真实运行时 smoke
- **WHEN** 运行 runtime consistency 集成协议
- **THEN** 覆盖新增指标、比率/去重指标、相对时间、Run Detail 与服务端 Lance READY/重启命中，并保存请求、状态、catalog/memory 观测和失败根因

#### Scenario: 事实真值稳定
- **WHEN** catalog reconciliation 在已有 seed 42 数据库执行
- **THEN** 受影响前后的事实表与旧窗口聚合 checksum/既有 R1 真值一致；若数据变化则门槛失败，不重取真值掩盖回归

#### Scenario: 高成本真实评测后置
- **WHEN** Python/Java 全量与确定性 contract/integrated smoke 尚未通过
- **THEN** 不启动 N=61 真实 LLM、integrated adversarial 或 real-session 高成本评测；全部确定性门槛通过后才运行并标注单轮方向性

