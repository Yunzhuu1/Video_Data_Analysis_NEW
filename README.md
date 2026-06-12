# ChatBI DataAgent Platform

本项目是一个面向短视频数据分析场景的企业级 ChatBI / DataAgent 平台。当前主线是把自然语言问题转换为可审计、可拦截、可重试、可评测的 SQL 分析链路。

项目采用双服务架构：

- Spring Boot 负责平台层能力：对外 API、SQL Gateway、SQL 硬校验、SQL 执行、DQ 软审核、运行记录、审批入口。
- Python Agent Engine 负责 Agent 编排：ChatBI 状态图、SQL 生成、校验反馈重试、高风险 SQL 等待审批、最终回答生成。

RAG 评论归因、重排模型、多层防御增强属于后续扩展方向。当前优先保证 ChatBI / Text2SQL 主链路真实可跑。

## 当前主链路

```text
User
  -> Spring Boot /api/agent/analyze
  -> LangGraphClient
  -> Python Agent Engine /analyze
  -> ROUTER
  -> SCHEMA
  -> SQL_GENERATE
  -> SQL_HARD_GUARD
  -> SQL_EXECUTE
  -> SQL_VALIDATE
  -> SQL_SOFT_DQ
  -> ANSWER
  -> AnalysisReport
```

高风险 SQL 会进入 `WAITING_APPROVAL` 状态，由 Spring Boot 审批接口恢复执行。

## 技术栈

| 层级 | 技术 |
|---|---|
| 平台层 | Spring Boot, Spring AI, MySQL, Redis, JSqlParser |
| Agent 引擎层 | Python, FastAPI, LangGraph-style state graph, httpx |
| LLM 接入 | OpenAI-compatible API, DeepSeek-compatible API, Ollama 可选 |
| 测试评测 | JUnit, pytest, ruff, eval runner |

## 项目结构

```text
.
├── src/                         # Spring Boot 平台层
│   ├── main/java/.../controller # 对外 API 与内部平台接口
│   ├── main/java/.../service    # SQL 校验、执行、DQ、运行记录等服务
│   └── test/java                # Java 单元测试
├── agent-engine/                # Python Agent Engine
│   ├── app/api                  # FastAPI 路由与 schema
│   ├── app/agents               # SQL / Answer 等 Agent
│   ├── app/clients              # 平台层与 LLM client
│   ├── app/graph                # ChatBI 状态图节点和状态
│   ├── app/prompts              # Prompt 模板
│   └── tests                    # Python 测试
├── docs/                        # 当前开发文档
├── docker-compose.yml
├── env.example
└── pom.xml
```

## 快速启动

### 1. 启动依赖

```powershell
docker compose up -d
```

### 2. 配置环境变量

参考 [env.example](env.example)。真实联调至少需要配置：

```powershell
$env:AI_API_KEY="your-api-key"
$env:AI_BASE_URL="https://api.deepseek.com"
$env:PLATFORM_CALLS_ENABLED="true"
```

### 3. 启动 Spring Boot

```powershell
mvn spring-boot:run
```

默认监听 `http://127.0.0.1:8080`。

### 4. 启动 Agent Engine

```powershell
cd agent-engine
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

默认监听 `http://127.0.0.1:8090`。

### 5. 真实链路请求

```powershell
$message = [uri]::EscapeDataString('分析各分类播放量趋势')
$url = "http://127.0.0.1:8080/api/agent/analyze?userId=demo&message=$message&nocache=true&engine=langgraph"
Invoke-RestMethod -Uri $url
```

更完整的联调步骤见 [docs/ChatBI真实联调手册.md](docs/ChatBI真实联调手册.md)。

## 本地检查

```powershell
mvn test

cd agent-engine
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m app.eval.runner --mode mock
```

## 核心文档

- [docs/ChatBI主链路开发设计.md](docs/ChatBI主链路开发设计.md)
- [docs/ChatBI真实联调手册.md](docs/ChatBI真实联调手册.md)
- [docs/服务接口契约.md](docs/服务接口契约.md)
- [docs/开发规范.md](docs/开发规范.md)
- [docs/DataAgent总体架构与迁移路线.md](docs/DataAgent总体架构与迁移路线.md)
- [agent-engine/README.md](agent-engine/README.md)

## 当前边界

- ChatBI / Text2SQL 是当前第一优先级。
- RAG 评论归因、Cross Validation、DBQA、复杂规则引擎是后续增强项。
- Python 引擎不直接访问数据库，所有确定性平台能力必须通过 Spring Boot 内部接口完成。
- 每个最小功能点独立提交，提交前至少运行相关 Java/Python 测试。
