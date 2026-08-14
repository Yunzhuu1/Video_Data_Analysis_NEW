## 1. 门禁 intent 入参 + 意图感知规则

- [x] 1.1 SqlValidateRequest/SqlGateResult 增加 intent 字段；/internal/sql/validate 接收 intent
- [x] 1.2 SqlStaticAnalyzer 接收 intent：intent=detail 且 intent.time_range 缺失或 type=="none" → 无条件 APPROVAL_NEEDED（与 SQL 形态无关；注意 time_range 有默认值，谓词必须覆盖 none）
- [x] 1.3 聚合意图豁免 LIMIT（intent ∈ aggregate/trend/ranking 或 SQL 含 GROUP BY/聚合函数 → DETAIL_QUERY_WITHOUT_LIMIT 不适用）
- [x] 1.4 单测：detail 无时间范围→审批、聚合无 LIMIT→不再误伤、聚合无时间范围→计划层兜底
- [x] 1.5 意图-形态一致性：intent ∈ aggregate/trend/ranking 但 SQL 无 GROUP BY/聚合且触碰 FACT → RETRYABLE，含单测

## 2. Python 透传 intent

- [x] 2.1 PlatformClient.validate_sql 增加 intent 参数并透传
- [x] 2.2 nodes.py SQL_HARD_GUARD 从 resolved_intent 取 intent 传入 validate_sql

## 3. 评测语义

- [ ] 3.1 runner：risk 类型用例收到 WAITING_APPROVAL 即 PASS
- [ ] 3.2 runner：非 risk 用例收到 WAITING_APPROVAL → 自动调审批放行 → 继续字段/关键词检查；**审批调用失败（超时/5xx）→ 该用例按 ERROR（环境性）处理，不计入 judged**
- [ ] 3.3 runner 报告增加 auto_released 计数/比例（与端到端并列展示）
- [ ] 3.4 cases.yaml：c04/c06/c10 期望按新语义（可放行后 PASS）；c18 期望 WAITING_APPROVAL（意图层确定性拦截）

## 4. 回答质量兜底

- [ ] 4.1 AnswerAgent：LLM 回答 metrics 为空时用查询结果 _basic_metrics 兜底
- [ ] 4.2 AnswerAgent：DQ 警告强制并入回答 warnings
- [ ] 4.3 单测：缺 metrics 兜底、DQ 警告必含

## 5. 回归与验收

- [ ] 5.1 Python pytest + ruff 全绿；Java mvn test 全绿
- [ ] 5.2 真实评测重跑：端到端 ≥ 90%；**同时记录 L2（避免选择性报告）**；c04/c06/c10 通过；c18 确定性拦截且核对 `debug.resolvedIntent.time_range.type=none`（归因：解析器 vs 门禁）；c11/c17 回答含 metrics/DQ 提示；auto_released 比例合理
- [ ] 5.3 更新 docs/eval-report.md 与 docs/开发日志.md
