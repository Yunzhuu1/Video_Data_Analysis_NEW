## MODIFIED Requirements

### Requirement: SQL 门禁统一三态裁决
Java 平台层 SHALL 提供统一的 SQL 门禁（`SqlGateService`），对候选 SQL 返回 `PASS / RETRYABLE / APPROVAL_NEEDED` 三态裁决；静态语义层（jsqlparser AST，基于语义层模型的表-列注册表与敏感列）先行，EXPLAIN 计划层（基于表类型感知）后行；分类权威在 Java 侧，Python 编排只做路由。门禁 SHALL 接收 `ResolvedIntent.intent` 作为入参，结合意图判定（detail 强制时间范围、聚合豁免 LIMIT）。

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

#### Scenario: 意图感知的明细规则
- **WHEN** 门禁收到 `intent` 入参
- **THEN** `intent=detail` 且 `intent.time_range` 缺失或 `type == "none"` → 无条件 `APPROVAL_NEEDED`（与 SQL 形态无关）；聚合意图豁免 LIMIT（`DETAIL_QUERY_WITHOUT_LIMIT` 不适用），时间范围规则仍生效；意图-形态不一致（聚合意图但 SQL 为明细形态触碰 FACT）→ `RETRYABLE`
