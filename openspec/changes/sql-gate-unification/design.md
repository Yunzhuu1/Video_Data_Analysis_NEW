## Context

真实评测（2026-08-13）定位到门禁三处断裂：
1. validate/execute 两套规则引擎割裂——`SQL_FULL_SCAN` 只在 execute 的 EXPLAIN 里产生，validate 的 approval_codes 里有它但永远触发不了（死代码）；
2. 性能规则藏在执行网关 → 聚合表（metric_daily）全扫被误报 HIGH → 重试 3 次耗尽 → 空回答（c02/c11/c14）；
3. 规则分散 5 组件、语法解析重复 3 次、`SqlRulesChecker` 用 `contains()` 字符串匹配、Python `_requires_human_approval()` 硬编码分类。

现状代码已用 jsqlparser（`SqlParserValidator`），且仅用了"解析+确认 SELECT"，具备扩展为完整 AST 静态层的条件。

## Goals / Non-Goals

**Goals:**
- 统一门禁为单一权威：Java `SqlGateService` 三态裁决，分类权威从 Python 挪进 Java。
- 语义层模型单源：表-列注册表（schema.sql 解析）+ 表类型 + 敏感列 + metric_definition，生成与校验共用，零业务库运行时依赖（EXPLAIN 除外）。
- 修复 validate/execute 不一致与聚合表全扫误报；EXPLAIN 风险可路由到 HITL 审批。
- 删 Python SQL_VALIDATE 节点；execute 只执行。

**Non-Goals:**
- 记忆系统 TEMPLATE_MATCH、Calcite 引入、多指标合成、SQL 优化器。

## Decisions

### D1: 三态契约与 DTO
`SqlGateResult`（Java record）：
```java
record SqlGateResult(String verdict,       // PASS | RETRYABLE | APPROVAL_NEEDED
                     String code,          // SQL_FULL_SCAN / SQL_EMPTY / SENSITIVE_FIELD_ACCESS ...
                     String reason,
                     String suggestion,
                     String riskLevel,
                     List<String> accessedTables) {}
```
`/internal/sql/validate` 端点保持路径不变，响应升级为 `SqlGateResult`（唯一调用方是 Python，无兼容负担）。`SqlExecutionService` **不再承担任何门禁检查**（删除 validate/SELECT/parse 前置检查），门禁仅在 `SQL_HARD_GUARD` 经 `/internal/sql/validate` 调用一次（见 D8 审批放行不变式）。

### D2: 语义层模型（SemanticModel）
- `TableSchemaRegistry`：启动时解析 `src/main/resources/schema.sql` 的 `CREATE TABLE` 语句 → `表名 → 列集合`；测试与 mock 共用同一解析（schema.sql 是唯一 DDL 源）。
- `TableType`：`AGGREGATE / FACT / DIM`，映射表（`metric_daily→AGGREGATE`，`user_behavior_fact/play_detail→FACT`，`*_dim→DIM`）；缺省 DIM 更安全？——未知表统一返回 `RETRYABLE`（LLM 臆测，重写优先；从严体现在绝不放行执行），避免漏判。
- `SENSITIVE_COLUMNS`：当前 `[user_id]`，配置可扩展。
- **SELECT `*`/表通配交互**：当 SELECT 含 `*`（或 `t.*`）且对应表的列集与敏感列相交 → `APPROVAL_NEEDED`（防止 `SELECT * FROM user_behavior_fact` 绕过敏感列检查）。
- 与 `metric_definition` 并列，语义层模型 = 指标字典 + 表-列注册表 + 表类型 + 敏感列。

### D3: 静态层规则（jsqlparser AST，无 DB）
按序短路：
1. 语法解析（现有 `SqlParserValidator` 保留）
2. SELECT-only（AST 类型判断，替换三处正则/关键字表）
3. 表存在性（AST `Table` 节点 vs `TableSchemaRegistry`）
4. 字段存在性（AST `Column` 节点 vs 表-列注册表；**最大实现风险，raw LLM 降级路径产出任意 SQL**）：
   - 别名解析：从 FROM/JOIN 的 `Table.getAlias()` 建 `别名→表` 映射，`a.col` 经映射解析
   - 子查询/派生表/CTE：只做外层表存在性，**列检查整体跳过**（内部列无法对注册表检查）
   - 表达式：只检查裸 `Column` 节点；`COUNT(*)`/函数参数按上述规则，解析不到即跳过
   - 裸列（无表限定）：FROM 仅单表时对该表解析；多表/无法判定时跳过（警告）——覆盖合成器事实路径的 `SELECT SUM(value) FROM user_behavior_fact ubf` 这类裸列
   - 兜底：任何解析不了的列引用 → **警告不阻断**（日志可观察）
5. 明细表规则（LIMIT/时间范围，AST 判断，替换正则）
6. 敏感列（AST SELECT 列 vs `SENSITIVE_COLUMNS`；`*`/`t.*` 且表含敏感列 → APPROVAL_NEEDED）
7. 逻辑规则（原 `SqlRulesChecker` 5 条迁移为 AST 规则：event_type 过滤 / JOIN 带 ON / GROUP BY 字段在 SELECT / 大表带 LIMIT / content 关联 creator）
失败分类：语法/表/字段 → `RETRYABLE`（LLM 可改）；**明细表无 LIMIT → `APPROVAL_NEEDED`；明细表无时间范围 → `APPROVAL_NEEDED`**（与 c19 期望对齐）；敏感列 → `APPROVAL_NEEDED`。

### D4: 计划层规则（EXPLAIN，静态层通过后执行）
`JdbcTemplate` 执行 `EXPLAIN <sql>`（安全，不执行查询）：
- `type=ALL`：按访问表的最高风险类型分类——FACT → `APPROVAL_NEEDED`；仅 AGGREGATE/DIM → `PASS`。
- `Using temporary` / `Using filesort` → `RETRYABLE`（suggestion 注入重生成 prompt）。
- `rows` 估算超阈值（如 100000）且访问 FACT → `APPROVAL_NEEDED`。
- 熔断（连续超时）保持在 execute，不进 gate。

### D5: SqlRulesChecker 处理
把 5 条 yml 字符串规则**迁移为代码内 AST 规则**（静态层第 7 条），退役 `SqlRulesChecker` + `sql-rules.yml`。
- 备选：保留 yml 配置化但评估器 AST 化 → 拒绝：本项目规则量小且固定，配置化收益低，字符串匹配的脆弱性才是问题；代码内 AST 规则可单测、可读、无解析层。

### D6: EXPLAIN 在 mock 评测与测试下的策略
- 评测 `--platform mock`：Python `PlatformClient` mock 直接返回 gate 结果（`platform_calls_enabled=false`），gate 的 EXPLAIN 不会执行——与现状一致。
- **mock 注入升级为三态**：`runner.py` 的 `_mock_guard`/`_mock_high_risk` 从旧两态契约（`pass/riskLevel/errorCode`）扩展为按 `verdict ∈ {PASS, RETRYABLE, APPROVAL_NEEDED}` 注入；新增"事实表全扫→WAITING_APPROVAL"正例靠注入 `verdict=APPROVAL_NEEDED` 驱动。
- Java 单测：`SqlGateService` 的 EXPLAIN 阶段抽成 `PlanAnalyzer` 接口，单测用内存 `JdbcTemplate` 桩或直接桩 `PlanAnalyzer` 返回模拟计划行；集成测试可选真 MySQL。
- 语义层静态规则单测不依赖 DB（纯 schema.sql 解析 + jsqlparser）。

### D7: Python 图改造
- `SQL_HARD_GUARD`：读 `verdict` —— PASS→execute；RETRYABLE→generate（feedback 注入）；APPROVAL_NEEDED→approval 节点。
- 删除 `SQL_VALIDATE` 节点及其边；`SQL_EXECUTE` 直接处理 `success`（失败=运行时错误 → retryable，max 重试后 answer）。
- `_requires_human_approval()` 移除（分类权威归 Java）。

### D8: 审批放行不变式（安全边界，必须显式）
- gate **只在图中调用一次**：`SQL_HARD_GUARD` 以 `allowHighRisk=false` 调 `SqlGateService`。
- `SQL_EXECUTE` **永不重跑 gate**：execute 内部不再调用门禁（删除重复校验），只执行+熔断。
- 审批通过后 resume：用**审批时刻的同一条 SQL** 直接 `SQL_EXECUTE`（`allowHighRisk=true` 仅为执行层透传），不再过 gate → 审批对象不漂移。
- 不变式必须配**回归测试**：构造"审批通过、但 SQL 若再过 gate 会被拦（如命中敏感列/全扫）"的用例，断言它照样执行。

## Risks / Trade-offs

- [字段存在性误报：函数/`*`/JSON 路径等合法列被拒] → AST 层放行 `*`、函数调用与 `COUNT(*)`；遇到无法解析的列引用降级为警告不阻断（日志可观察）。
- [schema.sql 与真实库漂移] → schema.sql 是 DDL 唯一源（AGENTS.md 已约束）；注册表单测断言覆盖所有已知表。
- [EXPLAIN 前置增加 DB 往返] → 只对通过静态层的 SQL 执行；EXPLAIN 安全（不执行查询）。
- [行为变化导致既有评测用例失败] → 本 change 内置评测适配（c15/c16 重写 + 新增正/反例），验收以重跑为准。
- [jsqlparser 方言边界] → 只放行 SELECT；门禁测试覆盖合成器与 raw LLM 典型 SQL。

## Migration Plan

1. 语义层模型（schema.sql 解析 + 表类型 + 敏感列 + 单测）。
2. SqlGateService 静态层（AST 规则迁移 + 三态）。
3. 计划层（PlanAnalyzer + EXPLAIN + 表类型感知审批）。
4. 端点与 execute 收敛；Python 图改造（三态路由、删 SQL_VALIDATE）。
5. 评测用例适配 + 全量回归（pytest/mvn）+ 真实评测重跑 + 文档。

## Open Questions

- `rows` 估算阈值是否需要可配置（yml/properties）？→ 先硬编码常量，后续需要再配置化。
- 未知表策略：统一为 `RETRYABLE`（LLM 臆测重写优先；从严体现在绝不放行），不再与 D2 矛盾。
