## MODIFIED Requirements

### Requirement: 单一 ChatBI 主线
系统 SHALL 只提供 ChatBI 主图（ROUTER → SCHEMA → SEMANTIC_RESOLVE → SQL_SYNTHESIZE（失败降级 SQL_GENERATE）→ SQL_HARD_GUARD → SQL_EXECUTE → SQL_SOFT_DQ → ANSWER），不得暴露 RAG/归因/DBQA 等全量图分支，且不得存在冗余的 SQL_VALIDATE 节点。

#### Scenario: 请求只走 chatbi 主图
- **WHEN** 客户端调用 Python `/analyze` 且不传 `graphMode`（或传 `chatbi`）
- **THEN** 引擎只执行 chatbi 主图节点，状态中不出现 `rag_result`、`cross_validation`、`insight_report`、`dbqa_*` 字段

#### Scenario: full 模式不再可用
- **WHEN** 客户端调用 Python `/analyze` 并传入 `graphMode=full`
- **THEN** 引擎忽略该模式并按 chatbi 主图执行（或返回参数不支持的错误），不得执行全量图

#### Scenario: 主图不含冗余校验节点
- **WHEN** 引擎构建 chatbi 主图
- **THEN** 图中不存在 `SQL_VALIDATE` 节点；SQL 执行结果的成败判定由 `SQL_EXECUTE` 直接承担

## ADDED Requirements

### Requirement: SQL 门禁统一三态裁决
Java 平台层 SHALL 提供统一的 SQL 门禁（`SqlGateService`），对候选 SQL 返回 `PASS / RETRYABLE / APPROVAL_NEEDED` 三态裁决；静态语义层（jsqlparser AST，基于语义层模型的表-列注册表与敏感列）先行，EXPLAIN 计划层（基于表类型感知）后行；分类权威在 Java 侧，Python 编排只做路由。

#### Scenario: 三态裁决
- **WHEN** 候选 SQL 进入门禁
- **THEN** 返回 `verdict ∈ {PASS, RETRYABLE, APPROVAL_NEEDED}` 及 `code/reason/suggestion/riskLevel`，Python 按三态路由（执行/重试/审批）

#### Scenario: 全扫按表类型分类
- **WHEN** EXPLAIN 判定 `type=ALL` 全表扫描
- **THEN** 访问 FACT/明细表（`user_behavior_fact`/`play_detail`）→ `APPROVAL_NEEDED`；仅访问 AGGREGATE（`metric_daily`）或 DIM 表 → `PASS`

#### Scenario: 敏感列访问需审批
- **WHEN** 候选 SQL 的 SELECT 列命中敏感列清单（当前含 `user_id`）
- **THEN** 门禁返回 `APPROVAL_NEEDED`

#### Scenario: 静态层不依赖业务库
- **WHEN** 门禁执行静态语义检查（语法/表/字段/敏感列/逻辑规则）
- **THEN** 仅使用语义层模型（`schema.sql` 解析的表-列注册表 + `metric_definition`），不查询业务数据表；EXPLAIN 仅在静态层通过后执行

#### Scenario: 审批放行不变式
- **WHEN** 一条 SQL 经 HITL 审批通过后 resume 执行
- **THEN** `SQL_EXECUTE` 直接执行审批时刻的同一条 SQL，不重新过门禁；gate 在图中仅在 `SQL_HARD_GUARD` 调用一次

#### Scenario: SELECT * 敏感列需审批
- **WHEN** 候选 SQL 的 SELECT 含 `*`（或 `t.*`）且对应表包含敏感列（如 `user_id`）
- **THEN** 门禁返回 `APPROVAL_NEEDED`

#### Scenario: 未知表可重试
- **WHEN** 候选 SQL 访问语义层模型不存在的表
- **THEN** 门禁返回 `RETRYABLE`（suggestion 提示重写），不放行执行

#### Scenario: 字段存在性宽容解析
- **WHEN** 候选 SQL 含别名引用、子查询/派生表/CTE 或复杂表达式中的列
- **THEN** 无法解析的列引用不阻断（降级为警告），仅对可解析且不在注册表中的列返回 `RETRYABLE`

#### Scenario: 明细表无时间范围需审批
- **WHEN** 候选 SQL 访问明细表且无时间范围过滤
- **THEN** 门禁返回 `APPROVAL_NEEDED`（与评测 c19 期望一致）
