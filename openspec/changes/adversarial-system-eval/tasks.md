## 1. Versioned Adversarial Manifest

- [ ] 1.1 定义 `adversarial_cases.json` schema/model/validator：固定 schema/truth dataset version、唯一 case ID、四层各5条、protocol/expected disposition-stage-code/node/order/function-call invariants/truth_source 必填；定义独立 observation_status 五态且仅OK可含六类disposition，在执行被测系统前 fail-fast，并增加缺字段、重复ID、层数错误、非法枚举/状态组合测试
- [ ] 1.2 人工编写20条独立 fixtures：S01-S05 重叠指标/别名/pinned>K/未知指标/prompt injection；P01-P05 反向edge/fan-out/非法ID重选/Candidate篡改/保留旧hash+version的三组件漂移variants；C01-C05 比率/同fact冲突/跨源/relative+HAVING/完整raw fallback契约；G01-G05 非SELECT/多风险审批/审批漂移/Planner持续故障耗尽重试/执行恢复；不得复制既有case扩充分母
- [ ] 1.3 为C01-C04以独立手工 SQL 直接查询 seed 42 MySQL，记录 expected_result、manual SQL、query time、dataset/seed version；增加审计测试证明 truth SQL 不来自系统 synthesized SQL，拒绝/审批/fallback 不配置或不进入R1

## 2. Protocol Adapters and Fault Isolation

- [ ] 2.1 实现统一 `AdversarialObservation` 与 question adapter，复用既有 graph/eval runner，采集 recall/ResolvedIntent/sql_source/node trace/plan/catalog/guard/approval/result；catalog 外 metric 或非SELECT执行作为 must-not 证据，不因最终SUCCESS被覆盖
- [ ] 2.2 实现 fixed_intent adapter，直接调用真实 Enumerator/selection/Validator/plan compiler/legacy synthesizer；不调用Semantic LLM；为SynthesisError增加不改变路由的state/Run Trace/debug观测字段（generic code+原始reason），覆盖C01-C05 stage/SQL/fieldRoutes及C05真实降级证据
- [ ] 2.3 实现白名单 mutated_plan adapter，以独立canonical oracle重算三组件实际hash但不替Validator拒绝；sentinel先记录compiler invocation/参数hash再阻断且受控异常不算adapter失败；Validator PASS时variant固定为OK+SYSTEM_ERROR+unsafe；P05 case_coverage/Expected按1个case且须3/3，variant_coverage/Audit/Unsafe/Illegal Rejection各固定3个机会
- [ ] 2.4 实现 raw_sql_or_fault adapter：integrated模式调用真实Spring门禁/审批契约；G04通过专用短生命周期子进程在import前设置LINEAGE_MAX_RETRIES=1/fail_count=2，父进程不改singleton，worker串行+timeout+全路径回收并输出effective config JSON；断言INVALID_PLAN_ID、retry_count=2+legacy派生reason、两次选择/校验、禁止compiler调用，并增加并行隔离测试

## 3. Comparator, Safety Redlines, and Reporting

- [ ] 3.1 实现profile preflight与observation/disposition两阶段comparator：preflight失败写profile级HARNESS_UNAVAILABLE且不创建伪case observations；profile启动后case先映射OK/PROFILE_INELIGIBLE/HARNESS_UNAVAILABLE/ADAPTER_ERROR/UNCLASSIFIED，仅OK再映射六类处置并比较stage/code/node/order/function invariants
- [ ] 3.2 实现按层 required audit fields 比较器，分别验证Semantic recall/mode、Planning hashes/candidates/validation/compiler invocation、Synthesis error code/reason/sql source/fallback、Safety verdict/approval/run trace；处置正确与Audit缺失分开计分，不把派生fallback reason冒充生产code
- [ ] 3.3 实现原子run journal/lease/ledger：STARTED前以case_id或case_id::variant_id构造key唯一registry并冻结分母，重复ID fail-fast；terminal observation以unit ID为幂等键create-only/CAS落盘，execution unit按PENDING→RUNNING→TERMINAL；增加process identity、heartbeat、lock与崩溃/超时/SIGKILL fixture
- [ ] 3.4 实现幂等finalizer与严格一一对应校验：补齐RUNNING/PENDING后验证record总数=registry基数且每unit恰好1条，missing/duplicate/unknown/orphan均0；duplicate即使同hash也Harness FAIL+LOCKED_INVALID且禁止聚合，保留冲突证据；重复finalize不得新增/删除/覆盖record或改变结果hash
- [ ] 3.5 实现聚合与JSON/Markdown报告：拆分case/variant coverage；COMPLETED计算正式产品指标，ABORTED仅报INCOMPLETE hits/locked denominator且accuracy=N/A，NOT_STARTED产品分母N/A；逐例证据、缺失集合断言和P1/P2 backlog不得自动改expected/产品

## 4. Reproducible Evaluation Profiles

- [ ] 4.1 为CLI增加profile/report/finalize参数；offline增加正常完成、异常、超时、SIGKILL后finalize、重复finalize，以及duplicate/orphan/unknown/missing terminal注入测试，断言一一对应与LOCKED_INVALID时不聚合；不改变既有runner参数行为
- [ ] 4.2 运行 offline 全20条manifest可加载测试及eligible确定性子集，要求 schema 20/20、eligible observation均OK、0 unclassified、非法计划/安全不变式门禁可复现；未执行的Spring/MySQL/LLM case标记PROFILE_INELIGIBLE并单列，不得冒充分母
- [ ] 4.3 为integrated实现case前Spring/MySQL preflight并运行：目标20/20 OK，C01-C04独立R1，G01-G03真实门禁/审批；preflight失败输出NOT_STARTED/NOT_COMPUTED，STARTED后中断保持锁定分母；两种均Harness FAIL/Readiness NOT_ASSESSED且不用mock替代
- [ ] 4.4 在 memory/embedding off 下仅对 S01-S05 与普通/实时 Planner 两例运行真实 LLM N=7，报告模型/配置/逐例原始结果并标注单轮方向性；发现产品失败只进backlog
- [ ] 4.5 运行既有 N=61 replay/mock、lineage offline、metric recall offline 与全量 Python/Java/ruff，证明新增 runner 对既有L1-L4/R1/sql_source/状态路由零行为回退；真实N=61仅在额度允许时补充且不作完成门槛

## 5. Evidence and Delivery

- [ ] 5.1 将双状态、安全红线、20条矩阵、真实N=7、独立R1、逐例失败/backlog与样本量边界整理进评测摘要、开发日志和面试素材库；若System Readiness失败必须如实保留，不宣称生产级红队或100%安全
- [ ] 5.2 运行 `openspec validate adversarial-system-eval --strict`、`git diff --check`，确认只修改评测/观测/测试/文档且未混入产品能力修复，勾选任务并提交（仅commit，由用户push/merge）
