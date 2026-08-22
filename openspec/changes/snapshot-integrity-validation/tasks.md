## 1. Snapshot 完整性核心

- [ ] 1.1 在 `catalog.py` 定义共享 integrity result/error：校验四个声明值存在且为64位小写hex，从当前内存内容按既有 canonical profile 重算 lineage/metric/schema/组合 hash，按固定 component 顺序返回 mismatch diagnostics
- [ ] 1.2 增加合法 snapshot、三类内容漂移、只改声明值、缺失/非法 hash、canonicalization 失败单测；复用跨语言 fixture 证明算法与现有 Java snapshot 生成结果一致

## 2. 三道执行边界

- [ ] 2.1 在 `PlanEnumerator` 入口调用共享校验；`plan_enumerate_node` 对专用完整性异常记录 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`、零候选、mismatchedComponents 与 legacy fallback，不以普通异常/NO_CANDIDATE 掩盖
- [ ] 2.2 在 `PlanValidator` 所有 candidate/ID 检查前调用共享校验并返回不可重试 `REJECT`；更新 graph 路由使该 verdict 不增加 planningRetryCount、不再进入 PLAN_SELECT且 plan compiler 仅接受 PASS
- [ ] 2.3 在 `synthesize_plan` 解析任何 snapshot ID 前重复校验，覆盖 Validator PASS 后内容再次变化的 TOCTOU 测试；失败不得生成部分 SQL并转换为既有可观测 SynthesisError/降级链路

## 3. 对抗回归闭环

- [ ] 3.1 更新 P05 adapter/expected 断言以消费真实 Validator 结果而不由 oracle 代拒绝；lineage/metric/schema 三 variants 必须 3/3 SAFE_REJECT、code一致、compiler invocation=false、unsafe pass=0/3
- [ ] 3.2 运行新的 adversarial offline hotfix profile/report，保留旧失败报告不改写；确认 case/variant coverage 与 audit 分母不因修复变化
- [ ] 3.3 运行 lineage offline、N=61 replay/mock 实现前后 behavior projection、全量 Python/Java/ruff，确认合法 snapshot 的 Path Recall、planId、SQL、L1-L4/R1/sql_source/状态路由零回退

## 4. 文档与交付

- [ ] 4.1 更新对抗评测摘要、开发日志和面试素材库，形成“P05 unsafe 3/3→0/3”的修复闭环；同时保留整体 Readiness 仍受其他 P2 影响的诚实边界
- [ ] 4.2 运行 `openspec validate snapshot-integrity-validation --strict`、`git diff --check`，确认未混入 Guard/未知指标等 P2 修复，勾选任务并提交（仅 commit，由用户 push/merge）
