## 1. MemoryStore namespace

- [x] 1.1 表加 namespace 列 + 唯一键 (norm_question, namespace)；upsert/find/all/delete/record_hit 按 namespace；存量迁移（默认 "default"）
- [x] 1.2 单测：namespace 隔离（同名不同 namespace 互不可见）、存量默认 default

## 2. 服务器记忆控制 API

- [x] 2.1 POST /internal/memory/seed（**拒绝 default** + intent pydantic 校验）、POST /internal/memory/clear（**幂等**）、GET /internal/memory/entries（X-Internal-Token 校验）
- [x] 2.2 单测：seed/clear/entries 按 namespace 生效、无 token 拒绝

## 2.5 Java 透传链（P1-1，real 模式全链路必需）

- [x] 2.5.1 AgentController.analyze 增加 @RequestParam(defaultValue="default") String memoryNamespace
- [x] 2.5.2 EngineAnalyzeRequest 增加 memoryNamespace 字段
- [x] 2.5.3 LangGraphClient 构造请求时透传 memoryNamespace
- [x] 2.5.4 Java 测试：默认/指定 namespace 透传断言

## 3. namespace 透传链

- [x] 3.1 /analyze 请求 + graph state 增加 memory_namespace（默认 "default"）
- [x] 3.2 语义解析读路径（_memory_pre_resolve）与写钩子按 namespace 读写
- [x] 3.3 run_real_case/run_graph_case 透传 memoryNamespace；单测：读/写按 namespace、不同 namespace 不串

## 4. eval runner 自隔离

- [x] 4.1 --memory on 使用 **per-eval namespace**（`eval-<eval_date>-<start_ts>`，一次评测一个）；启动时 clear 该 namespace（real 走 API / mock 走本地）
- [x] 4.2 run_counterexample 改为毒化变体：seed {问题文本 X, intent metrics 不一致}；查询 X（相似度 1.0）→ metrics 一致性校验拦截（band != hit）；real 走 POST seed、mock 写本地
- [x] 4.3 单测：eval namespace 生成、seed/clear 调用路径

## 5. 评测与回归

- [x] 5.1 Python pytest + ruff 全绿；Java mvn test 全绿
- [x] 5.2 全量 --memory on 自隔离重跑（重复对 PASS、反例真预置 PASS、命中率 > 0、L1-L4 不回退）；default 记忆前后不变
  - 实测：--memory on 命中率 20%、c24 重复对 PASS、c25 毒化反例 PASS、default 零污染；--memory off L1-L3 100%、default 零污染（runner 始终用 eval namespace）
- [x] 5.3 --memory off 回归 L1-L4 100% 不回退
  - 实测：--memory on 命中率 20%、c24 重复对 PASS、c25 毒化反例 PASS、default 零污染；--memory off L1-L3 100%、default 零污染（runner 始终用 eval namespace）
- [x] 5.4 更新 docs/eval-report.md 与 docs/开发日志.md
