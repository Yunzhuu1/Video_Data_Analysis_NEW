## MODIFIED Requirements

### Requirement: 多入口真实模块执行
对抗 runner SHALL 按 `question | fixed_intent | mutated_plan | raw_sql_or_fault` protocol 调用对应真实生产模块，并保存统一 observation；每个 observation SHALL 先声明 `OK | PROFILE_INELIGIBLE | HARNESS_UNAVAILABLE | ADAPTER_ERROR | UNCLASSIFIED` 状态，只有 `OK` 才可进入六类系统 disposition。mutation/fault SHALL 使用可审计白名单，不得通过任意回调绕过生产 Validator、Compiler、门禁或图路由。P05 三类 snapshot 内容漂移 SHALL 由真实生产完整性校验全部拒绝，harness oracle 只提供独立证据而不得替产品拒绝。

#### Scenario: 固定意图隔离模型方差
- **WHEN** Planning 或 Synthesis case 提供人工 ResolvedIntent
- **THEN** runner 绕过 Semantic LLM，只评估目标确定性阶段并记录实际 candidate/path/SQL/trace

#### Scenario: 篡改计划不能进入编译器
- **WHEN** case 注入反向 edge、fan-out、非法 plan ID、Candidate 字段篡改或 snapshot 漂移
- **THEN** runner 使用真实 Validator/重选逻辑处置，未验证计划不得访问 plan compiler 或 SQL execute

#### Scenario: 三类快照内容漂移全部安全拒绝
- **WHEN** P05 分别替换 lineage、metric definitions、schema projection 内容并故意保留旧组件hash与catalogVersion
- **THEN** harness canonical oracle 证明三个variant的实际内容hash与声明hash不一致，且真实 Validator 3/3 返回 `REJECT/SNAPSHOT_INTEGRITY_MISMATCH`、actual_disposition=SAFE_REJECT、compiler_invocation_attempted=false、unsafe_pass=false；harness 不得代替生产 Validator 拒绝或移动 expected

#### Scenario: P05同时提供case与variant分母
- **WHEN** 汇总P05的lineage/metric/schema三个variant
- **THEN** case_coverage与Expected Disposition按case计1个固定分母且仅3/3均OK/均符合才命中；variant_coverage、Audit Completeness、Unsafe Pass、Illegal Plan Rejection按variant各计3个固定机会并逐项展示，任一variant非OK只减少numerator而不得缩小任一denominator

#### Scenario: 真实门禁与故障适配
- **WHEN** Safety/Recovery case 提供 raw SQL、审批恢复或接口故障
- **THEN** integrated profile 调用真实 Spring 门禁/审批契约或受控接口 fault double，记录 verdict/code、SQL hash、重试与节点轨迹
