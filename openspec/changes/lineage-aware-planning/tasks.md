## 1. Versioned Lineage Catalog

- [x] 1.1 新增 `src/main/resources/lineage_catalog.json`，以稳定 ID 覆盖 MVP tables/grains、date/category/content/creator bindings、定向 `fromTable/fromColumns → toTable/toColumns` N:1/1:1 edges，以及 total_plays/total_likes/completion_rate/video_revenue（可选 creator_revenue）的 daily/fact/detail paths；固定 cardinalityFromTo、supported intents、expression/event/time refs、freshness 与 cost，禁止复制第二份 mock catalog
- [x] 1.2 实现 Spring `LineageCatalogService`/snapshot DTO/`GET /internal/lineage/snapshot`：校验 ID/引用唯一性与 `TableSchemaRegistry` 表列存在性；冻结 lineage、规范化 metric definitions、schema projection，计算三个子 hash 与组合 catalogVersion；按固定 canonical JSON profile 增加跨语言 fixture/expected hash 测试，并覆盖合法资源、未知字段、metric 定义改动导致版本变化与 fail-fast
- [x] 1.3 实现 Python lineage snapshot 模型与 PlatformClient real/mock loader；mock 读取同一 Java resource并构造等价 metric/schema projection，增加测试断言 Java/Python fixture canonical bytes/hash、组合版本、三个子 hash及 path/binding/edge 集合一致

## 2. Deterministic Plan Space and Constrained Planner

- [x] 2.1 实现 `CandidateQueryPlan`/`fieldRoutes`/rejection 模型与 `PlanEnumerator`：为 dimension/filter/ordering/time 的每种 usage 保存完整 route；单指标 aggregate/trend/ranking、从 metric source 仅沿有向 outgoing N:1/1:1 edge 做最大两跳稳定 BFS、最多 5 个候选、组合 catalogVersion 参与 canonical plan hash、稳定排序去重和结构化 legality/rejected reasons
- [x] 2.2 增加 Enumerator 单测：源表直接 creator、play_detail→content→creator 两跳、video_revenue→content.category、`dimensions=[] + category filter` 仍保存 filter route、ordering/time route 完整性、预聚合向 content/creator 的 1:N fan-out 拒绝、content_dim→play_detail 反向边拒绝、未知 binding、三跳、多指标/detail 进入 legacy fallback，且重复运行 plan ID/顺序稳定
- [x] 2.3 实现独立 `QueryPlannerAgent` 与版本化 `query-planning-v1` skill：严格消费只读 question/ResolvedIntent/candidate summary/feedback，只输出候选 selected_plan_id + 枚举 reason/explanation/confidence；增加 FakeLLM 测试证明不接受 LLM 自造 table/column/join/SQL/path
- [x] 2.4 实现选择路由与 `PlanValidator`：0 候选=LEGACY_FALLBACK、1=AUTO_SINGLE、同 freshness 下 Pareto 支配=AUTO_POLICY、真实 cost/freshness 取舍=PLANNER_AGENT；用同一冻结 snapshot 重算 candidate/catalog/metric/全部 field usage/edge 正向语义/hop/compiler 约束，缺失 filter/order/time route、反向 edge、非法 ID 或版本漂移最多重选一次后 legacy，并覆盖全部裁决测试

## 3. Graph Integration and Plan-driven Compilation

- [x] 3.1 在 settings（含无 pydantic 兼容分支）增加 `LINEAGE_PLANNING_MODE=off|shadow|active` 和规划上限；扩展 `DataAgentState` 保存冻结的 lineage+metric definitions+schema projection 组合 snapshot/version、三个子 hash、candidate/rejected plans、selection/validation/retry/edge/fallback 与 Planner 成本字段
- [x] 3.2 调整 Semantic Resolver 维度契约与 Prompt：per-metric dimensions 仅为 native 提示，用户明确的全局逻辑维度必须保留；增加“每位创作者的完播率”等测试，确保 creator 不因 completion_rate 原生维度为 content 而被删除
- [x] 3.3 为既有确定性合成器增加窄的 validated-plan 编译入口：仅从 run 冻结 metric definitions 与 selected plan fieldRoutes 解析主/fact表达式、event/time、source、dimension/filter/ordering/time binding 和 JOIN；禁止自行 BFS、回读可变 catalog 或调用 `_resolve_path()` 覆盖计划，复用 WHERE/HAVING/time/group/order 格式化；测试 category filter 无 dimensions、creator completion、category video revenue、daily/fact likes SQL 在 MySQL 可解析执行
- [x] 3.4 将 `PLAN_ENUMERATE → 条件 PLAN_SELECT → PLAN_VALIDATE` 接入 LangGraph；active+PASS 走 plan compile，off/shadow/多指标/detail/零候选/重选耗尽走 legacy，legacy 失败才 raw SQL；限制 planning retry=1，保持 SQL_HARD_GUARD/HITL 审批恢复不变并增加图路由/恢复回归测试
- [x] 3.5 扩展 Python AnalyzeResponse/routes、Spring EngineAnalyzeResponse/Controller debug 与 Run Trace，透传组合 catalogVersion、lineage/metric/schema hash、candidate fieldRoutes/rejected plans、selectedPlanId、selectionSource、planner reason/skill、validation、retry、edge IDs、legacy fallback 与可归因成本；默认 includeDebug=false 契约不变，增加 Python/Java API 契约测试

## 4. Independent Path Evaluation and Regression

- [x] 4.1 新增 8~10 条人工独立标注 `lineage_cases.yaml`：普通/实时分类点赞量、内容/创作者播放量、创作者完播率、无 dimensions 的分类 filter、分类视频收益、ordering/time route、危险 fan-out/反向 edge、非法 plan ID、一次重选和无支持路径；golden metricPath/fieldRoutes/edge/selection 不得由 Enumerator 反向生成
- [x] 4.2 扩展 eval runner：固定 ResolvedIntent 离线报告 Path Recall，按多候选 judged 子集报告 Plan Selection Accuracy，另报 Illegal Plan Rejection/Replan Success/Planner Invocation/selection source/legacy fallback 与逐例 rejected reasons；Planner prompt chars/latency/token 只按可归因阶段计量
- [x] 4.3 运行全量 Python/Java 测试、ruff 与 OpenSpec strict；在 planning=off 证明 N=61/R1/SQL/路由相对 metric-recall 基线零行为回退，在 shadow 逐例比较候选计划与 legacy SQL但不改变执行结果
- [x] 4.4 在 embedding/memory 关闭下运行 active：离线 path hard gates 全绿、非法计划拒绝 100%，真实 Planner 仅跑普通/实时取舍用例并标注单轮方向性；全量 N=61 报 L1-L4/ERROR/sql_source/selection/fallback，R1 保持 29/29，任何回退逐例审计

## 5. Documentation and Delivery

- [x] 5.1 将“信任 LLM 选择、不允许发明事实”、双 Agent 分工、完整 fieldRoutes、定向安全 JOIN、组合 snapshot/cross-language hash、回退、path/R1 原始计数与 MVP 局限整理进开发日志、metrics report、面试素材库和一份可复现架构/A-B 摘要；不得把单轮 Planner 波动或单指标两跳 MVP 包装成生产级自进化/完整血缘平台
- [x] 5.2 运行 `openspec validate lineage-aware-planning --strict`、确认全部任务勾选、`git diff --check` 和工作区范围后提交实现（仅 commit，由用户 push/merge）
