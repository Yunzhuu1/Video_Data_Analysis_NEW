## 1. Versioned Adversarial Manifest

- [ ] 1.1 定义 `adversarial_cases.json` schema/model/validator：固定 schema/truth dataset version、唯一 case ID、四层各5条、protocol/expected disposition-stage-code/node/order invariants/truth_source 必填；定义独立 observation_status 五态且仅OK可含六类disposition，在执行被测系统前 fail-fast，并增加缺字段、重复ID、层数错误、非法枚举/状态组合测试
- [ ] 1.2 人工编写20条独立 fixtures：S01-S05 重叠指标/别名/pinned>K/未知指标/prompt injection；P01-P05 反向edge/fan-out/非法ID重选/Candidate篡改/保留旧hash+version的三组件漂移variants；C01-C05 比率/同fact冲突/跨源/relative+HAVING/完整raw fallback契约；G01-G05 非SELECT/多风险审批/审批漂移/Planner持续故障耗尽重试/执行恢复；不得复制既有case扩充分母
- [ ] 1.3 为C01-C04以独立手工 SQL 直接查询 seed 42 MySQL，记录 expected_result、manual SQL、query time、dataset/seed version；增加审计测试证明 truth SQL 不来自系统 synthesized SQL，拒绝/审批/fallback 不配置或不进入R1

## 2. Protocol Adapters and Fault Isolation

- [ ] 2.1 实现统一 `AdversarialObservation` 与 question adapter，复用既有 graph/eval runner，采集 recall/ResolvedIntent/sql_source/node trace/plan/catalog/guard/approval/result；catalog 外 metric 或非SELECT执行作为 must-not 证据，不因最终SUCCESS被覆盖
- [ ] 2.2 实现 fixed_intent adapter，直接调用真实 Enumerator/selection/Validator/plan compiler/legacy synthesizer；不调用 Semantic LLM，并覆盖 C01-C05 与固定 Planning 输入的 stage/SQL/fieldRoutes 观测
- [ ] 2.3 实现白名单 mutated_plan adapter（reverse_edge、fanout_cardinality、invalid_plan_id、candidate_field_replace、snapshot_component_replace），以独立canonical oracle重算lineage/metric/schema实际hash并记录mutation前后值但不替Validator拒绝；调用真实Validator/一次重选，以compiler sentinel记录并阻止漏检后的测试执行，三组件variant 3/3单列
- [ ] 2.4 实现 raw_sql_or_fault adapter：integrated 模式调用真实 Spring SQL validate/审批契约，fault double 仅在 Planner/execute 接口边界注入 malformed/timeout/error；G04按lineage_max_retries+1持续失败并验证两次选择/校验后legacy，区分各observation_status与产品SYSTEM_ERROR，覆盖审批前节点顺序和审批/恢复 SQL hash

## 3. Comparator, Safety Redlines, and Reporting

- [ ] 3.1 实现 observation/disposition 两阶段 comparator：先唯一映射OK/PROFILE_INELIGIBLE/HARNESS_UNAVAILABLE/ADAPTER_ERROR/UNCLASSIFIED，仅OK再映射六类处置并比较 stage、code、must-visit/must-not-visit/required order；同例多个门禁原因按fixture预先声明首个API code判定
- [ ] 3.2 实现按层 required audit fields 比较器，分别验证 Semantic recall/mode、Planning hashes/candidates/validation、Synthesis SQL source/fallback、Safety verdict/approval/run trace；处置正确与Audit缺失分开计分
- [ ] 3.3 实现双状态聚合：按profile eligible cases报告Observation Coverage和各非OK状态；Harness FAIL时Readiness=NOT_ASSESSED，仅Harness PASS计算PASS/FAIL；四层Expected Disposition、Unsafe Pass、Illegal Plan Rejection、Graceful Fallback、Recovery Success、Audit Completeness、R1均输出原始分子/分母，禁止因非OK静默缩分母
- [ ] 3.4 生成 JSON 原始报告和 Markdown 摘要，逐例展示 expected/actual、stage/code、trace invariant、truth/audit/result；readiness失败自动生成只读P1/P2 backlog（case/evidence/severity），不得自动修改expected或产品实现

## 4. Reproducible Evaluation Profiles

- [ ] 4.1 为 CLI 增加 `--adversarial-profile offline|integrated|directional-real` 与 report 参数；offline 禁用 LLM/embedding/数据库并验证 manifest、mutation、comparator、aggregation，新增 runner 单测且不改变既有参数行为
- [ ] 4.2 运行 offline 全20条manifest可加载测试及eligible确定性子集，要求 schema 20/20、eligible observation均OK、0 unclassified、非法计划/安全不变式门禁可复现；未执行的Spring/MySQL/LLM case标记PROFILE_INELIGIBLE并单列，不得冒充分母
- [ ] 4.3 在真实 Spring+MySQL 环境运行 integrated：目标20/20 observation_status=OK，C01-C04 R1使用独立真值，G01/G02/G03走真实门禁/审批；如环境不可用以HARNESS_UNAVAILABLE、Harness FAIL、Readiness NOT_ASSESSED交付，不用mock替代
- [ ] 4.4 在 memory/embedding off 下仅对 S01-S05 与普通/实时 Planner 两例运行真实 LLM N=7，报告模型/配置/逐例原始结果并标注单轮方向性；发现产品失败只进backlog
- [ ] 4.5 运行既有 N=61 replay/mock、lineage offline、metric recall offline 与全量 Python/Java/ruff，证明新增 runner 对既有L1-L4/R1/sql_source/状态路由零行为回退；真实N=61仅在额度允许时补充且不作完成门槛

## 5. Evidence and Delivery

- [ ] 5.1 将双状态、安全红线、20条矩阵、真实N=7、独立R1、逐例失败/backlog与样本量边界整理进评测摘要、开发日志和面试素材库；若System Readiness失败必须如实保留，不宣称生产级红队或100%安全
- [ ] 5.2 运行 `openspec validate adversarial-system-eval --strict`、`git diff --check`，确认只修改评测/观测/测试/文档且未混入产品能力修复，勾选任务并提交（仅commit，由用户push/merge）
