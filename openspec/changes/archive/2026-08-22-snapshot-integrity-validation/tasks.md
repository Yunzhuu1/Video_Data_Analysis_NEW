## 1. Snapshot 完整性核心

- [x] 1.1 在 `catalog.py` 定义共享 integrity result/error：校验四个声明值存在且为64位小写hex，从当前内存内容按既有 canonical profile 重算 lineage/metric/schema/组合 hash及包含声明+内容的snapshotFingerprint，按固定 component 顺序返回 mismatch diagnostics
- [x] 1.2 增加合法 snapshot、三类内容漂移、只改声明值、缺失/非法 hash、canonicalization 失败单测；复用跨语言 fixture 证明算法与现有 Java snapshot 生成结果一致

## 2. 三道执行边界

- [x] 2.1 在 `PlanEnumerator` 入口调用共享校验，将实际snapshotFingerprint写入Candidate并纳入planId；`plan_enumerate_node` 对专用完整性异常记录 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`、零候选、components 与 legacy fallback
- [x] 2.2 在 `PlanValidator` 所有 candidate/ID 检查前调用共享校验并返回不可重试 `REJECT`，PASS返回validated fingerprint；更新graph状态/路由使REJECT不增加retry、不进入PLAN_SELECT且已有code不被NO_CANDIDATE覆盖
- [x] 2.3 在 `synthesize_plan` 入口复制并校验私有snapshot，强制私有副本fingerprint=validated fingerprint=plan fingerprint后递归冻结且只读冻结对象；测试自洽S1替换S0仍拒绝、冻结后修改原对象不影响SQL
- [x] 2.4 增加 graph 级失配 snapshot 测试，使用 fake platform 与 Planner/plan-compiler/Guard spies 断言有序路径 `PLAN_ENUMERATE→PLAN_VALIDATE(REJECT)→SQL_SYNTHESIZE(legacy)→SQL_HARD_GUARD`、retry=0、PLAN_SELECT=0、plan compiler=0，并验证 integrity code/components 原样保留

## 3. 对抗回归闭环

- [x] 3.1 更新 P05 adapter/expected 断言以消费真实 Validator 结果而不由 oracle 代拒绝；lineage/metric/schema 三 variants 必须 3/3 SAFE_REJECT、code一致、compiler invocation=false、unsafe pass=0/3
- [x] 3.2 运行新的 adversarial offline hotfix profile/report，保留旧失败报告不改写；确认 case/variant coverage 与 audit 分母不因修复变化
- [x] 3.3 运行 lineage offline、N=61 replay/mock 实现前后 behavior projection、全量 Python/Java/ruff，确认 Path Recall/SQL/L1-L4/R1/sql_source/状态路由零回退；planId仅验证同snapshot重复枚举稳定并记录纳入fingerprint后的一次预期版本变化

## 4. 文档与交付

- [x] 4.1 更新对抗评测摘要、开发日志和面试素材库，形成“P05 unsafe 3/3→0/3”的修复闭环；同时保留整体 Readiness 仍受其他 P2 影响的诚实边界
- [x] 4.2 运行 `openspec validate snapshot-integrity-validation --strict`、`git diff --check`，确认未混入 Guard/未知指标等 P2 修复，勾选任务并提交（仅 commit，由用户 push/merge）
