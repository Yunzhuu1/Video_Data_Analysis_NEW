## Why

项目已有 N=61 端到端、49 条 `golden_spec`、10 条独立血缘用例以及各层单测，但证据分散且主要回答“正常问题是否正确”，尚不能统一证明异常输入、非法计划、能力边界和运行故障发生时，系统能否在正确阶段成功执行、安全拒绝、等待审批、受控降级或恢复，并留下可归因记录。秋招阶段继续扩架构的边际收益低于建立一套跨层、独立真值、诚实报告失败的对抗评测协议。

## What Changes

- 新增 20 条独立对抗样本，按 Semantic/Recall、Planning/Lineage、SQL Synthesis、Safety/Recovery 四层各 5 条组织，不把既有普通用例重复计入新分母。
- 新增多入口评测协议：自然语言 `question`、固定 `ResolvedIntent`、篡改 Candidate/Snapshot、raw SQL/故障注入；每条固定 expected disposition/stage/code、must-visit/must-not-visit nodes 与 truth source。
- 统一最终处置为 `EXECUTE_SUCCESS | SAFE_REJECT | APPROVAL_REQUIRED | SUPPORTED_FALLBACK | RECOVERED | SYSTEM_ERROR`，将 Harness 完整性与 System Adversarial Readiness 分开判定。
- 扩展评测报告，分别展示 Expected Disposition、Unsafe Pass、R1、Illegal Plan Rejection、Graceful Fallback、Recovery Success、Audit Completeness 的原始计数和逐例诊断；拒绝/审批/fallback 不进入 R1 分母。
- 固定评测卫生：可执行结果真值来自独立手工 SQL，path/处置 golden 人工填写且不得由被测系统反向生成；真实 LLM 仅跑 5 条 Semantic 与 2 条 Planner 取舍，标注 N=7 单轮方向性，其余为确定性硬证据。
- 冻结评测与产品修复边界：本 change 只修 harness、fixture、fault adapter 和缺失审计字段；产品能力失败进入 P1/P2 backlog，安全漏洞另开 hotfix，不在同一 change 中移动 expected 追求全绿。

## Capabilities

### New Capabilities
- `adversarial-system-eval`: 定义跨层对抗样本、多入口执行、处置分类、安全红线、独立真值和系统 readiness 报告契约。

### Modified Capabilities
- `agent-eval`: 扩展既有 runner/report，使其能调度 question、fixed intent、mutated plan/snapshot、raw SQL/fault injection 四类协议，并验证运行轨迹完整性。

## Impact

- 主要影响 `agent-engine/app/eval/`、对应 Python 测试、Java SQL 门禁/审批的测试适配器、评测报告与开发/面试文档。
- 不修改生产指标目录、Planner/Compiler/门禁的业务行为，不引入图数据库、embedding、HITL 澄清、新 Skill 自动发布或新的运行时依赖。
- 真实 LLM 调用固定为 N=7 方向性观测；完整 N=61 采用 replay/mock 做确定性零回退，额度允许时的真实 N=61 仅为可选补充。
