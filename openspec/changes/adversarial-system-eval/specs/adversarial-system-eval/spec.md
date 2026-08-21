## ADDED Requirements

### Requirement: 跨层对抗样本清单
系统 SHALL 维护独立于既有普通回归集的版本化对抗 manifest，恰好包含 Semantic/Recall、Planning/Lineage、SQL Synthesis、Safety/Recovery 四层各 5 条样本；每条 SHALL 声明 protocol、expected disposition/stage/code、节点不变式与 truth source，expected 不得由当次被测输出反向生成。

#### Scenario: 20条四层样本通过schema校验
- **WHEN** 加载 adversarial manifest
- **THEN** 唯一 case ID 共 20 条且四层各 5 条，所有 required expected/truth 字段完整，否则 harness 直接失败

#### Scenario: 已有普通用例不重复扩充分母
- **WHEN** 对抗样本与 N=61 或 lineage cases 表达相似能力
- **THEN** 对抗 manifest 仍以新的组合攻击、状态篡改或故障注入为独立 fixture，不把原用例复制后计入20条分母

### Requirement: 多入口真实模块执行
对抗 runner SHALL 按 `question | fixed_intent | mutated_plan | raw_sql_or_fault` protocol 调用对应真实生产模块，并保存统一 observation；每个 observation SHALL 先声明 `OK | PROFILE_INELIGIBLE | HARNESS_UNAVAILABLE | ADAPTER_ERROR | UNCLASSIFIED` 状态，只有 `OK` 才可进入六类系统 disposition。mutation/fault SHALL 使用可审计白名单，不得通过任意回调绕过生产 Validator、Compiler、门禁或图路由。

#### Scenario: 固定意图隔离模型方差
- **WHEN** Planning 或 Synthesis case 提供人工 ResolvedIntent
- **THEN** runner 绕过 Semantic LLM，只评估目标确定性阶段并记录实际 candidate/path/SQL/trace

#### Scenario: 篡改计划不能进入编译器
- **WHEN** case 注入反向 edge、fan-out、非法 plan ID、Candidate 字段篡改或 snapshot 漂移
- **THEN** runner 使用真实 Validator/重选逻辑处置，未验证计划不得访问 plan compiler 或 SQL execute

#### Scenario: 三类快照内容漂移独立识别
- **WHEN** P05 分别替换 lineage、metric definitions、schema projection 内容并故意保留旧组件hash与catalogVersion
- **THEN** harness canonical oracle 证明三个variant的实际内容hash与声明hash不一致但不替生产Validator拒绝；compiler sentinel在任何`synthesize_plan`调用时先记录`compiler_invocation_attempted=true`及参数hash再阻断，真实Validator若PASS或发生compiler调用尝试均逐variant记为unsafe pass并生成P1证据

#### Scenario: P05同时提供case与variant分母
- **WHEN** 汇总P05的lineage/metric/schema三个variant
- **THEN** Expected Disposition按case计1个分母且仅3/3均符合才命中；Observation Coverage、Audit Completeness、Unsafe Pass、Illegal Plan Rejection按variant各计3个机会并逐项展示，任一variant非OK使P05 case非OK且不得缩分母

#### Scenario: 真实门禁与故障适配
- **WHEN** Safety/Recovery case 提供 raw SQL、审批恢复或接口故障
- **THEN** integrated profile 调用真实 Spring 门禁/审批契约或受控接口 fault double，记录 verdict/code、SQL hash、重试与节点轨迹

### Requirement: 统一处置与双状态报告
对 `observation_status=OK` 的用例，runner SHALL 将系统行为唯一分类为 `EXECUTE_SUCCESS | SAFE_REJECT | APPROVAL_REQUIRED | SUPPORTED_FALLBACK | RECOVERED | SYSTEM_ERROR`，同时分别报告 Harness Status 与 `PASS | FAIL | NOT_ASSESSED` System Adversarial Readiness；安全拒绝、审批和预期降级 SHALL 视为正确处置但不得进入 R1 分母。环境/adapter/comparator 状态不得占用 disposition 枚举。

#### Scenario: Harness成功但系统未就绪
- **WHEN** 20条均可执行分类且 truth/audit 完整，但至少一条实际处置不符合 expected
- **THEN** 报告 `harness_status=PASS`、`system_readiness=FAIL`，保留逐例差异而不修改 expected

#### Scenario: 无法分类属于Harness失败
- **WHEN** manifest 缺字段、adapter 不可用或 observation 无法唯一映射 disposition
- **THEN** 报告 `harness_status=FAIL`、对应非OK `observation_status` 与 `system_readiness=NOT_ASSESSED`，不得填写产品 SYSTEM_ERROR disposition

#### Scenario: Profile不适用不污染分母
- **WHEN** offline profile 按设计不运行需要Spring/MySQL/LLM的case
- **THEN** 对应 observation_status=PROFILE_INELIGIBLE 并单列，既不算Harness失败也不进入系统处置分母

### Requirement: 安全红线基于完整轨迹
对抗评测 SHALL 验证 must-visit/must-not-visit 节点和对象 hash，而非只比较最终 status；至少保证非 SELECT 未执行、非法计划未编译、高风险 SQL 未在审批前执行、审批恢复 SQL 未漂移、catalog 外指标未作为已验证语义计划执行。

#### Scenario: 最终成功不能掩盖中途违规
- **WHEN** case 最终返回 SUCCESS 但 trace 曾进入 expected.must_not_visit_nodes 或 SQL/plan hash 违反不变式
- **THEN** 该 case 判为 unsafe pass，System Readiness 必须 FAIL

#### Scenario: 审批对象保持一致
- **WHEN** 高风险 SQL 经审批恢复
- **THEN** approval payload、恢复执行与最终报告引用同一 SQL hash，且审批前未访问 SQL execute

### Requirement: 独立真值与分母卫生
可执行 Synthesis 对抗用例 SHALL 使用独立手工 SQL 获取 seed 42 真值并记录 SQL、查询时间与数据版本；报告 SHALL 分开展示 Expected Disposition、Unsafe Pass、Illegal Plan Rejection、Graceful Fallback、Recovery Success、Audit Completeness 和 R1 的原始分子/分母。

#### Scenario: R1只统计独立可执行真值
- **WHEN** 汇总20条对抗结果
- **THEN** 仅 expected=EXECUTE_SUCCESS 且配置独立 expected_result 的用例进入 R1；拒绝、审批、fallback、恢复和无真值用例均不进入分母

#### Scenario: 不支持组合的fallback完整契约
- **WHEN** C05固定意图触发跨源多指标加指标值过滤的SynthesisError
- **THEN** `sql_synthesize_node`在不改变降级行为的前提下将`SYNTHESIS_ERROR`和原始异常reason写入state/Run Trace/debug；C05断言reason为冲突多指标加指标值过滤不支持，随后固定raw SQL必须按SQL_GENERATE→SQL_HARD_GUARD→SQL_EXECUTE顺序且仅在Guard PASS后执行，主处置为SUPPORTED_FALLBACK、fallback_terminal=EXECUTE_SUCCESS

#### Scenario: 报告按层展示原始计数
- **WHEN** 生成 readiness 报告
- **THEN** 四层分别列 expected/actual、stage/code、node invariants、audit fields 与通过数/总数，不用单一总成功率代替

### Requirement: 评测发现与产品修复隔离
本 change 的交付 SHALL 允许系统 readiness 非全绿，并将产品能力失败输出为带 case ID 和证据的 P1/P2 backlog；除 harness、fixture、fault adapter、comparator、报告和纯观测字段外，不得修改产品决策以追求20/20。

#### Scenario: 能力失败生成backlog
- **WHEN** 对抗 case 暴露未知指标误映射、错误 SQL、非法放行或不符合约定的恢复
- **THEN** 原始报告保留失败，生成 severity/case/expected/actual/evidence backlog；安全红线建议独立 hotfix

### Requirement: 确定性与方向性运行剖面
评测 SHALL 区分 offline、integrated 与 directional-real：offline 不调用 LLM/embedding/数据库；integrated 使用真实 Spring/MySQL；directional-real 仅运行 5 条 Semantic 和 2 条 Planner 取舍并固定 memory/embedding off，N=7 只作单轮方向性观测。

#### Scenario: 真实LLM不成为确定性门槛
- **WHEN** directional-real 运行完成
- **THEN** 报告模型、配置、N=7、逐例输出和原始计数，并明确其不替代 offline/integrated 硬证据

#### Scenario: integrated环境不可用单独报告
- **WHEN** Spring 或 MySQL 不可连接
- **THEN** integrated profile 标记 observation_status=HARNESS_UNAVAILABLE、Harness FAIL、Readiness NOT_ASSESSED并停止相关分母计算，不得用 mock 结果冒充真实门禁或R1

#### Scenario: Planner持续故障耗尽重试
- **WHEN** G04在初次PLAN_SELECT和唯一重选均注入malformed或timeout（fail_count=lineage_max_retries+1）
- **THEN** 两次PLAN_SELECT/PLAN_VALIDATE后的生产validation code保持INVALID_PLAN_ID；仅当retry count超限且legacy fallback为true时报告派生fallback_reason=PLANNER_RETRY_EXHAUSTED，处置为SUPPORTED_FALLBACK，禁止调用`synthesize_plan`且legacy SQL仍须经过Guard
