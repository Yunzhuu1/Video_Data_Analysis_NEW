## 1. Java 侧观测透传

- [x] 1.1 AnalysisReport 增加可空 status 字段（含 getter/setter）
- [x] 1.2 EngineAnalyzeResponse 增加 sqlSource 字段
- [x] 1.3 AgentController 正常路径：报告置 status=SUCCESS，includeDebug 时 debug 增加 sqlSource
- [x] 1.4 AgentController 等待审批路径：等待报告置 status=WAITING_APPROVAL，includeDebug=true 时组装 debug{resolvedIntent, sqlRetryCount, sqlSource}
- [x] 1.5 更新 AnalysisReportMappingTest 覆盖新字段与等待路径透传

## 2. Python 侧 sql_source 透传

- [x] 2.1 schemas.py AnalyzeResponse 增加 sqlSource 字段
- [x] 2.2 routes.py analyze/approve 返回 sqlSource=state.get("sql_source")
- [x] 2.3 更新 test_api_routes 覆盖 sqlSource 透传

## 3. eval runner 观测修正

- [x] 3.1 run_real_case 正确读取 status（payload.status）
- [x] 3.2 run_real_case 读取 resolvedIntent（debug/payload 兜底）
- [x] 3.3 run_real_case 读取 sqlSource 并写入 state 与返回结果

## 4. 回归验证与文档

- [x] 4.1 Python pytest 58/58（新增 run_real_case 观测解析测试）+ ruff clean
- [x] 4.2 Java mvn test 16/16（新增 AgentController 等待路径 + EngineAnalyzeResponse 映射测试）
- [x] 4.5 Spring LangGraphClient 引擎超时 90s→180s（修复真实 LLM 慢导致的偶发 500，评测可用性 21/21 的阻塞项）
- [x] 4.3 真实评测重跑（--llm real --platform real）：可用性 100%（21/21）、status 列与 agent_run 一致、Source 列有值、L1=100%。注：c18 因 LLM 本次未触发审批而诚实 FAIL（护栏行为，非观测问题）
- [x] 4.4 更新 docs/eval-report.md（15:08 最终快照）与 docs/开发日志.md（BUG-005 修复 + BUG-006 发现）
