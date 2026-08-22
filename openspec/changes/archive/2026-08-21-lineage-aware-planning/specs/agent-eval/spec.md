## ADDED Requirements

### Requirement: 血缘规划分层评测
评测 SHALL 使用人工独立标注的 lineage path cases 分别测量 Enumerator、Planner 与 Compiler：固定 ResolvedIntent 的 Path Recall 不受 Semantic LLM 方差影响；Plan Selection Accuracy 只在多候选 judged 子集计算；非法计划拒绝与一次重选单列原始计数；golden path/edge 不得由被测 Enumerator 反向生成。

#### Scenario: 固定意图测 Path Recall
- **WHEN** 对具有 golden metricPath/fieldRoutes/edge IDs 的 path cases 运行离线 Enumerator
- **THEN** 报告候选是否包含完整 golden plan，展示命中数/总数与逐例 rejected reasons，不调用 LLM、embedding 或数据库

#### Scenario: Planner 选择准确率
- **WHEN** path case 提供多个合法候选及 expected selected plan/preference
- **THEN** 只在该 judged 子集报告 Plan Selection Accuracy 原始分子/分母，并区分 AUTO_POLICY 与 PLANNER_AGENT

#### Scenario: 非法计划与重选协议
- **WHEN** FakeLLM 返回伪造 plan ID 或首个候选被注入 validation failure
- **THEN** 报告 Illegal Plan Rejection 与 Replan Success 原始计数，断言未验证计划未进入 compiler

### Requirement: 血缘规划端到端回归与成本口径
评测 SHALL 在 planning off/shadow/active 下报告 N=61 的 L1-L4、ERROR、sql_source、selection source、Planner invocation、legacy fallback、规划重试和可归因成本，并保持既有 R1 可断言子集结果不回退。真实 Planner LLM 单轮正确率/延迟变化 SHALL 标注方向性；无法按阶段归因的总 token 不得冒充 Planner 成本。

#### Scenario: Off 模式零行为回退
- **WHEN** `LINEAGE_PLANNING_MODE=off` 运行既有 N=61
- **THEN** SQL/状态路由与 change 前基线一致，新增规划字段为空或明确 off

#### Scenario: Active 模式结果回归
- **WHEN** active 模式运行 N=61 且覆盖路径由新 compiler 生成
- **THEN** 报告全量与覆盖子集，R1 保持 29/29、ERROR 不增加，任何 legacy fallback 均按原因逐例展示

#### Scenario: Planner 成本独立计量
- **WHEN** 某用例实际调用 QueryPlannerAgent
- **THEN** 报告 planner prompt chars、latency 与可可靠归因的 token；AUTO_SINGLE/AUTO_POLICY 用例 planner 调用成本为零

