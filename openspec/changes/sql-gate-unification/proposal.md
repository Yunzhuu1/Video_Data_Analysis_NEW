## Why

真实评测（2026-08-13）暴露 SQL 质量门禁的系统性问题：validate/execute 两套规则引擎割裂（`SQL_FULL_SCAN` 只在 execute 检查，validate 产生不了该 code，AGENTS.md 中"SQL_FULL_SCAN→审批"契约是死代码）、性能规则藏在执行网关导致聚合表全扫误报与重试耗尽空回答、规则分散在 5 个 Java 组件且语法解析重复 3 次、`SqlRulesChecker` 用字符串匹配。门禁不统一，评测数字无法如实反映系统能力。

## What Changes

- **语义层模型底座**：从 `schema.sql` 解析表-列注册表；表类型分类（AGGREGATE/FACT/DIM）；敏感列清单（`user_id` 起步）；与 `metric_definition` 构成单源，供 SQL 生成与门禁共用（零业务库运行时依赖）。
- **SqlGateService 统一门禁**：Stage1 静态层（现有 jsqlparser AST 扩展：语法/SELECT/表存在/字段存在/明细规则/敏感列/逻辑规则 AST 化，`SqlRulesChecker` 迁移）；Stage2 计划层（EXPLAIN：FULL_SCAN 按表类型 FACT→APPROVAL / AGGREGATE→PASS，TEMP_TABLE/FILESORT→RETRYABLE 带建议，大行数且 FACT→APPROVAL）；返回 `PASS/RETRYABLE/APPROVAL_NEEDED` 三态。
- **端点与图改造**：`/internal/sql/validate` 升级为 gate 三态；execute 只执行+熔断；Python `HARD_GUARD` 按三态路由、`EXECUTE` 纯执行、**删除 SQL_VALIDATE 节点**；分类权威从 Python 挪进 Java。
- **评测适配**：更新 c15/c16 期望（gate 重试/审批语义）；新增"事实表全扫→WAITING_APPROVAL"正例、"聚合表全扫→PASS"反例。
- **文档**：AGENTS.md 门禁契约更新、`docs/开发日志.md`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `chatbi-mainline`: 主图移除 `SQL_VALIDATE` 节点、纳入语义解析路径；新增「SQL 门禁统一三态裁决」需求（gate 契约、表类型感知审批、敏感列）。
- `agent-eval`: 门禁行为评测用例适配（c15/c16 重写、新增全扫审批正例/聚合全扫反例）。

## Impact

- **Java**：`SqlValidationService`→`SqlGateService`、`SqlParserValidator`（AST 扩展）、`SqlRulesChecker`（迁移/退役）、`SqlExecutionService`（只执行）、新增语义模型组件（表-列注册表/表类型/敏感列）、`internal` 端点。
- **Python**：`graph/nodes.py`（HARD_GUARD 三态路由、删 SQL_VALIDATE）、`graph/graph_builder.py`（去 SQL_VALIDATE 边）、`app/eval/cases.yaml`（c15/c16/新用例）。
- **评测**：`docs/eval-report.md`（重跑快照）、`docs/开发日志.md`。
- **验证**：Python pytest + ruff、Java `mvn test`、真实评测重跑（需 DeepSeek 余额）。
- **非目标**：记忆系统 TEMPLATE_MATCH 节点、引入 Calcite（沿用现有 jsqlparser）、多指标合成、SQL 优化器。
