## Why

指标召回已经把自然语言稳定映射到候选 metric code，但 `ResolvedIntent` 到物理表/字段/JOIN 的路径仍散落在 `_resolve_path()`、`_field_expr()` 与 SQL 合成分支中；当同一指标存在预聚合/事实表路径或维度需要跨表时，系统只能靠硬编码选择，既难审计也无法让 Agent 根据“实时/低成本”等用户偏好做受约束决策。现在需要用一个收敛的血缘规划 MVP，把合法物理路径显式化，并让独立 Planner Agent 只在合法候选中选择，而不是让 LLM 发明数据库事实。

## What Changes

- 新增 Git 版本化的 `lineage_catalog.json`，以稳定 ID 描述 MVP 表粒度、指标物理路径、维度绑定、定向 N:1/1:1 JOIN 边、freshness 与 cost；Spring 将 lineage overlay、编译所需 metric definitions 与 schema projection 冻结为同一不可变 snapshot，以跨语言固定 canonical JSON 规则计算组合 `catalogVersion`，Python mock/real 消费同一版本语义。
- 在现有 `ResolvedIntent` 后增加轻量 `PlanEnumerator → QueryPlannerAgent（条件调用）→ PlanValidator → SQL compile`：0 个计划走旧链路、1 个计划自动选择、多个但默认策略可判时自动选择，仅存在真实语义取舍时调用 Planner LLM。
- Planner 只能返回候选中的 `selected_plan_id` 与 reason，禁止修改 ResolvedIntent、输出表/列/JOIN/SQL 或创造 ID；非法选择/验证失败最多重选一次，之后回退现有 `_resolve_path()`/raw SQL 链路。
- MVP 只覆盖单指标 aggregate/trend/ranking，date/category/content/creator，最多两跳且仅沿不复制指标行的 N:1/1:1 方向；重点解锁 creator 完播率、分类视频收益，并演示普通/实时分类点赞量的 daily/fact 路径取舍。
- Semantic Resolver 忠实抽取用户明确表达的逻辑维度，不再因为指标当前原生表维度较窄而静默删除；物理可达性由 Planner 判断。
- 每个 CandidateQueryPlan 保存 dimension/filter/ordering/time 的完整 `fieldRoutes`，Validator 与 Compiler 只能消费已选计划中的 route，不得在编译阶段重新 BFS；增加 catalog/候选/选择来源/理由/验证/重试/route/edge ID/legacy fallback 的 debug 与 Run Trace，并新增独立 golden path 评测及 N=61、R1=29 子集回归。
- 不引入图数据库、MySQL 血缘管理平台、完整表达式 DSL、多指标血缘规划、自动 Skill 发布或前端。

## Capabilities

### New Capabilities

- `lineage-aware-planning`: 版本化最小血缘目录、合法单指标计划枚举、受约束 Planner Agent 选路、计划验证、旧链路回退与可审计观测。

### Modified Capabilities

- `semantic-resolution`: Semantic Agent 与物理路径规划解耦，逻辑维度忠实抽取；已覆盖查询可由选定 QueryPlan 驱动确定性 SQL 编译，未覆盖查询保持既有合成/降级行为。
- `chatbi-mainline`: 主图在语义解析与 SQL 合成之间增加条件式血缘规划节点，同时保持 Python 唯一编排和既有门禁/HITL 路径。
- `agent-eval`: 增加 path recall、plan selection、非法计划拒绝、Planner 调用/重选/legacy fallback 与规划成本口径，并以固定 ResolvedIntent 隔离 Planner 评测。

## Impact

- Spring Boot：新增 lineage catalog loader/validator、规范化 metric/schema snapshot、组合版本 hash DTO 与内部只读 API；扩展 `TableSchemaRegistry` 或校验适配以验证 JOIN 两端表列，现有数据库业务表不变。
- Python Agent Engine：新增 lineage snapshot/model、PlanEnumerator、QueryPlannerAgent/Skill、PlanValidator 与编排节点；`DataAgentState`、debug/API/Java透传增量增加规划观测字段。
- SQL 合成：只为 MVP 覆盖路径增加基于 selected plan 的编译入口；既有 `synthesize()` 保留为未覆盖/失败时的兼容 fallback，多指标代码不重写。
- 评测：新增 8~10 条人工独立标注的 path cases；Planner 单测使用固定 ResolvedIntent，端到端继续报告 N=61 L1-L4/ERROR/sql_source 与 R1 29/29，真实 Planner LLM 结果标注单轮方向性。
- 依赖与存储：不新增图数据库或在线模型；血缘资源为 JSON，使用现有 Jackson/Python JSON 能力，不新增 MySQL 表。
