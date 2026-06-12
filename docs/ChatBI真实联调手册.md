# ChatBI 真实联调手册

本文用于验证 M11：`PLATFORM_CALLS_ENABLED=true` 时，Spring Boot 平台层与 Python Agent Engine 以真实内部接口完成 ChatBI 主链路。

## 1. 前置条件

必须可用：

```text
MySQL        127.0.0.1:3306
Redis        127.0.0.1:6379
Spring Boot  127.0.0.1:8080
Agent Engine 127.0.0.1:8090
```

可选：

```text
AI_API_KEY   配置后启用真实 LLM SQL/Answer 生成
```

无 `AI_API_KEY` 时，Agent Engine 会使用 deterministic fallback SQL 和 Answer，仍可验证真实平台调用链路。

## 2. Agent Engine 环境变量

在 `agent-engine/.env` 中配置：

```text
SERVICE_NAME=agent-engine
PLATFORM_BASE_URL=http://127.0.0.1:8080
INTERNAL_API_TOKEN=dev-internal-token
TRACE_CALLBACK_ENABLED=true
PLATFORM_CALLS_ENABLED=true
AI_BASE_URL=https://api.deepseek.com
AI_API_KEY=
AI_MODEL=deepseek-chat
```

## 3. 启动顺序

先启动 MySQL 和 Redis，再启动 Spring Boot，最后启动 Agent Engine。

Spring Boot：

```powershell
mvn spring-boot:run
```

Agent Engine：

```powershell
cd agent-engine
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

## 4. 健康检查

Agent Engine：

```powershell
Invoke-RestMethod http://127.0.0.1:8090/health
```

预期：

```json
{
  "status": "UP",
  "service": "agent-engine"
}
```

Spring Boot：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/actuator/health
```

## 5. 真实 ChatBI 请求

```powershell
$message = [uri]::EscapeDataString('分析各分类播放量趋势')
$url = "http://127.0.0.1:8080/api/agent/analyze?userId=demo&message=$message&nocache=true&engine=langgraph"
Invoke-RestMethod -Uri $url
```

预期链路：

```text
Spring /api/agent/analyze
  -> Python /analyze
  -> Spring /internal/schema/relevant
  -> Spring /internal/sql/validate
  -> Spring /internal/sql/execute
  -> Spring /internal/dq/sql-result/check
  -> Python AnswerNode
  -> Spring final report
```

## 6. 验收点

必须确认：

```text
1. 返回体包含 runId。
2. status 为 SUCCESS 或 WAITING_APPROVAL。
3. finalReport 包含 summary/sql/metrics/charts/warnings。
4. Run Trace 至少包含：
   ROUTER
   SCHEMA
   SQL_GENERATE
   SQL_HARD_GUARD
   SQL_EXECUTE
   SQL_VALIDATE
   SQL_SOFT_DQ
   ANSWER
5. SQL 审计表 agent_audit_log 中存在本次 SQL 记录。
6. DQ warning 能进入 finalReport.warnings。
```

## 7. 高风险 SQL 审批验证

构造会触发明细表高风险的请求，例如：

```powershell
$message = [uri]::EscapeDataString('查询播放明细')
$url = "http://127.0.0.1:8080/api/agent/analyze?userId=demo&message=$message&nocache=true&engine=langgraph"
Invoke-RestMethod -Uri $url
```

预期：

```text
status = WAITING_APPROVAL
approvalReason 包含 SQL hard guard 风险原因
SQL_EXECUTE 节点不会在审批前执行
```

审批通过：

```powershell
$runId = '<替换为返回的 runId>'
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8080/api/agent/runs/$runId/approval" `
  -ContentType 'application/json' `
  -Body '{"approved":true}'
```

预期：

```text
审批通过后恢复 SQL_EXECUTE
执行请求 allowHighRisk=true
最终返回 SUCCESS
```

## 8. 常见问题

如果 Spring 调 Python 失败：

```text
确认 LangGraphClient 使用 HTTP/1.1。
确认 agent-engine 监听 127.0.0.1:8090。
确认 /analyze 请求体是 JSON。
```

如果 Python 调 Spring 失败：

```text
确认 PLATFORM_CALLS_ENABLED=true。
确认 PLATFORM_BASE_URL=http://127.0.0.1:8080。
确认 INTERNAL_API_TOKEN 与 Spring 配置一致。
```

如果 SQL 被拦截：

```text
查看 finalReport.summary、approvalReason、Run Trace 中 SQL_HARD_GUARD 节点输出。
这是预期行为，说明 Java 平台层硬兜底生效。
```
