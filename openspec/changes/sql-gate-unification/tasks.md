> 里程碑纪律：阶段 1-5 各自独立提交；每阶段完成时该侧测试全绿（1-3 Java / 4 Python / 5 全量）。

## 1. 语义层模型底座

- [x] 1.1 实现 schema.sql 解析 → 表-列注册表（TableSchemaRegistry），含单测
- [x] 1.2 表类型分类（AGGREGATE/FACT/DIM，含未知表从严策略）
- [x] 1.3 敏感列清单（user_id 起步，可配置扩展）

## 2. SqlGateService 静态层（jsqlparser AST）

- [x] 2.1 SqlGateResult 三态 DTO + /internal/sql/validate 升级为 gate 契约
- [x] 2.2 AST 规则：语法/SELECT-only/表存在性/字段存在性（替换三处重复检查）
- [x] 2.3 AST 规则：明细表 LIMIT/时间范围（替换正则）
- [x] 2.4 AST 规则：敏感列访问 → APPROVAL_NEEDED
- [x] 2.5 迁移 SqlRulesChecker 5 条逻辑规则为 AST 规则，退役 yml 字符串检查
- [x] 2.6 字段存在性：别名解析（别名→表映射）、子查询/CTE 跳过列检查、表达式只查裸列、**裸列规则（单表解析/多表跳过）**；测试覆盖合成器事实路径 `SELECT SUM(value) FROM user_behavior_fact ubf` 与 raw LLM 任意 SQL
- [x] 2.7 SELECT * / 表通配且表含敏感列 → APPROVAL_NEEDED，含测试
- [x] 2.8 未知表 → RETRYABLE（suggestion 提示），含测试

## 3. 计划层（EXPLAIN + 表类型感知审批）

- [x] 3.1 PlanAnalyzer 接口（EXPLAIN 可桩，测试不依赖 DB）
- [x] 3.2 FULL_SCAN 按表类型分类：FACT→APPROVAL / AGGREGATE/DIM→PASS
- [x] 3.3 TEMP_TABLE/FILESORT→RETRYABLE（带建议）；大行数且 FACT→APPROVAL
- [x] 3.4 SqlExecutionService 收敛为只执行+熔断（删除重复 validate/SELECT/parse）
- [x] 3.5 审批放行不变式回归测试：审批通过的 SQL 即使再过 gate 会被拦也照样执行

## 4. Python 图改造

- [ ] 4.1 SQL_HARD_GUARD 按三态路由（PASS/RETRYABLE/APPROVAL_NEEDED）
- [ ] 4.2 删除 SQL_VALIDATE 节点及其边；EXECUTE 直接承担成败判定；清理 state.py 的 validation_feedback 字段与 nodes.py 写入点
- [ ] 4.3 移除 _requires_human_approval()（分类权威归 Java）
- [ ] 4.4 图测试迁移到 gate 三态契约（test_graph_flow 9 处 validate_sql 引用 / 5 处 monkeypatch 点重写；4 处 validation_feedback 断言同步更新）

## 5. 评测适配与回归

- [ ] 5.1 更新 c15/c16 期望为 gate 三态语义
- [ ] 5.2 mock 三态注入机制（runner _mock_guard 升级按 verdict）+ 新增用例：事实表全扫→WAITING_APPROVAL 正例、聚合表全扫→PASS 反例
- [ ] 5.3 Python pytest + ruff 全绿；Java mvn test 全绿（含新增门禁/语义模型测试）
- [ ] 5.4 真实评测重跑：可用性 21/21、c02 类不再重试耗尽、端到端较 47.62% 提升、**风险类用例 100% 进入 WAITING_APPROVAL（高风险拦截率 100%）**
- [ ] 5.5 更新 AGENTS.md 门禁契约与 docs/开发日志.md
