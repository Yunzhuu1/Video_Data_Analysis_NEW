# Spring Boot 平台层设计

## 1. 定位

Spring Boot 平台层不是 Agent 编排层，而是企业级数据平台能力的承载层。

它负责：

- 对外 API。
- 用户身份与权限。
- SQL 安全执行。
- 指标字典。
- Schema 元数据。
- 语义缓存。
- Run Trace。
- 审计日志。
- 慢查询与运维统计。

LangGraph Agent Engine 调用平台层完成所有确定性操作，尤其是 SQL 执行、指标查询和运行状态记录。

## 2. 模块划分

推荐最终包结构：

```text
com.yunzhu.dataagent.platform
├── controller
│   ├── AnalysisController
│   ├── AgentRunController
│   ├── MetricController
│   ├── InternalSqlController
│   ├── InternalSchemaController
│   └── InternalRunController
├── service
│   ├── LangGraphClient
│   ├── SqlExecutionService
│   ├── SqlAuditService
│   ├── MetricCatalogService
│   ├── SchemaCatalogService
│   ├── AgentRunTraceService
│   ├── AgentRunQueryService
│   ├── PermissionService
│   └── SemanticCacheService
├── domain
│   ├── AgentRun
│   ├── AgentRunNode
│   ├── MetricDefinition
│   ├── AuditLog
│   └── DataPermissionPolicy
├── dto
│   ├── AnalyzeRequest
│   ├── AnalyzeResponse
│   ├── SqlExecuteRequest
│   ├── SqlExecuteResult
│   ├── AgentRunSummary
│   └── AgentRunDetail
└── config
    ├── WebClientConfig
    ├── RedisConfig
    ├── DataSourceConfig
    └── ObservabilityConfig
```

当前项目可以不立即改包名，先按模块新增类，等架构稳定后再整体移动。

## 3. 核心数据表

### 3.1 agent_run

记录一次完整分析请求。

```sql
CREATE TABLE agent_run (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    question TEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    current_node VARCHAR(64),
    final_report JSON,
    error_message TEXT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    total_duration_ms BIGINT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_status_created (status, created_at)
);
```

状态：

```text
RUNNING
SUCCESS
FAILED
CANCELED
WAITING_APPROVAL
```

### 3.2 agent_run_node

记录每个 Agent 节点执行状态。

```sql
CREATE TABLE agent_run_node (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    node_name VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    input_payload MEDIUMTEXT,
    output_payload MEDIUMTEXT,
    error_message TEXT,
    model_name VARCHAR(128),
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    duration_ms BIGINT,
    retry_count INT DEFAULT 0,
    started_at DATETIME,
    finished_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_node_status (node_name, status),
    INDEX idx_created_at (created_at)
);
```

节点状态：

```text
PENDING
RUNNING
SUCCESS
FAILED
SKIPPED
WAITING_APPROVAL
```

### 3.3 agent_audit_log

记录用户问题、生成 SQL 和访问的数据资产。

```sql
CREATE TABLE agent_audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    sql_text TEXT,
    accessed_tables VARCHAR(512),
    accessed_columns TEXT,
    risk_level VARCHAR(32),
    decision VARCHAR(32),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_user_created (user_id, created_at)
);
```

### 3.4 metric_definition

指标字典。

```sql
CREATE TABLE metric_definition (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    metric_name VARCHAR(128) NOT NULL,
    metric_code VARCHAR(128) NOT NULL UNIQUE,
    business_definition TEXT NOT NULL,
    formula TEXT NOT NULL,
    dimensions JSON,
    time_granularity VARCHAR(32),
    owner VARCHAR(64),
    version INT NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 4. 核心服务设计

### 4.1 AgentRunTraceService

职责：

- 创建 run。
- 开始节点。
- 完成节点。
- 失败节点。
- 跳过节点。
- 标记等待审批。
- 完成 run。

接口建议：

```java
String startRun(String userId, String question);

Long startNode(String runId, String nodeName, Object input);

void finishNode(Long nodeId, Object output, NodeTokenUsage usage);

void failNode(Long nodeId, Throwable error);

void skipNode(String runId, String nodeName, String reason);

void markWaitingApproval(String runId, String nodeName, Object approvalContext);

void finishRun(String runId, Object finalReport);

void failRun(String runId, Throwable error);
```

要求：

- 所有 payload 使用 ObjectMapper 序列化。
- payload 过大时截断或落对象存储，数据库只保存 preview。
- `finishNode` 必须记录耗时。
- 节点失败不能吞异常，必须向上抛给调用方。

### 4.2 AgentRunQueryService

职责：

- 查询最近运行记录。
- 查询某个 run 详情。
- 查询节点列表。
- 查询失败节点。
- 聚合统计成功率、平均耗时。

典型接口：

```java
List<AgentRunSummary> listRecentRuns(int limit);

AgentRunDetail getRunDetail(String runId);

List<AgentRunNodeDetail> getRunNodes(String runId);

AgentRunStats getStats(LocalDateTime from, LocalDateTime to);
```

### 4.3 SqlExecutionService

职责：

- 接收结构化 SQL 执行请求。
- 做 SQL 只读校验。
- 做 AST/规则校验。
- 做权限校验。
- 做 EXPLAIN 风险评估。
- 执行 SQL。
- 返回结构化结果。
- 写审计和慢查询。

请求：

```java
class SqlExecuteRequest {
    String runId;
    String userId;
    String question;
    String sql;
    String purpose;
    boolean allowHighRisk;
}
```

结果：

```java
class SqlExecuteResult {
    boolean success;
    String sql;
    List<String> columns;
    List<Map<String, Object>> rows;
    int rowCount;
    boolean truncated;
    List<String> warnings;
    String error;
    String riskLevel;
    List<String> accessedTables;
    long durationMs;
}
```

规则：

- 禁止多语句。
- 禁止 DDL/DML。
- 禁止访问未授权表。
- 大表明细查询必须有 LIMIT。
- 聚合查询必须明确指标口径。
- 高风险 SQL 默认不执行，返回 `riskLevel=HIGH`。

### 4.4 MetricCatalogService

职责：

- 查询指标定义。
- 按自然语言匹配指标。
- 返回公式、维度、口径说明。
- 支持指标版本。

典型接口：

```java
MetricDefinition findByName(String metricName);

List<MetricDefinition> search(String keyword);

MetricDefinition create(MetricCreateRequest request);

MetricDefinition update(String metricCode, MetricUpdateRequest request);
```

### 4.5 SchemaCatalogService

职责：

- 从 INFORMATION_SCHEMA 加载表结构。
- 缓存 Schema。
- 根据问题返回相关 Schema。
- 返回外键关系、枚举值、字段注释。

LangGraph 初期可以调用：

```http
GET /internal/schema/full
POST /internal/schema/relevant
```

后期可以扩展血缘关系：

```text
table -> upstream jobs -> downstream metrics -> reports
```

## 5. API 设计

### 5.1 对外 API

```http
POST /api/analyze
GET  /api/runs
GET  /api/runs/{runId}
GET  /api/metrics
GET  /api/metrics/{metricCode}
```

### 5.2 内部 API

仅供 LangGraph 调用。

```http
POST /internal/sql/execute
GET  /internal/schema/full
POST /internal/schema/relevant
GET  /internal/metrics/{metricName}
POST /internal/runs
POST /internal/runs/{runId}/nodes
PATCH /internal/runs/{runId}/nodes/{nodeId}
POST /internal/audit/log
```

内部 API 必须鉴权，可以先用共享 token：

```http
X-Internal-Token: ${INTERNAL_API_TOKEN}
```

## 6. 配置规范

主配置不允许包含真实密钥和生产默认值。

```yaml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
```

开发便利配置放在 `application-dev.yml`。

测试 profile 必须避免依赖真实外部服务：

```yaml
app:
  data-initializer:
    enabled: false
  slow-query:
    enabled: false
```

## 7. 兼容策略

迁移期间保留旧类：

- `DataAnalysisAgent`
- `CoordinatorAgent`
- `SqlExecutionTool`
- `RAGAgent`

但新主链路应变为：

```text
AnalysisController -> LangGraphClient -> agent-engine
```

旧链路只作为 fallback 或调试入口。

## 8. 验收清单

- `mvn test` 通过。
- `/api/analyze` 能创建 run。
- `/api/runs/{runId}` 能查询完整节点状态。
- `/internal/sql/execute` 可独立执行并返回结构化结果。
- 高风险 SQL 不会直接执行。
- 所有 SQL 有审计日志。
- 测试环境不依赖真实模型、Redis、MySQL 初始化逻辑。
