# ChatBI DataAgent Platform

本项目是一个面向短视频数据分析场景的企业级 ChatBI / DataAgent 平台。当前主线是把自然语言问题转换为可审计、可拦截、可重试、可评测的 SQL 分析链路。

项目采用双服务架构：

- Spring Boot 负责平台层能力：对外 API、SQL Gateway、SQL 硬校验、SQL 执行、DQ 软审核、运行记录、审批入口。
- Python Agent Engine 负责 Agent 编排：ChatBI 状态图、SQL 生成、校验反馈重试、高风险 SQL 等待审批、最终回答生成。

当前主线是 ChatBI 主链路：语义解析（NL -> ResolvedIntent）+ 确定性 SQL 合成 + 安全护栏 + HITL 审批，编排基于 LangGraph，评测 harness（golden_spec + 四层评分 + FakeLLM 录制回放 + A/B 对比）已就绪（见 [docs/Agent编排与架构设计.md](docs/Agent编排与架构设计.md) 与 [EVALUATION.md](EVALUATION.md)）。RAG 评论归因、交叉验证等全量图分支已下线。

## 当前主链路

```text
User
  -> Spring Boot /api/agent/analyze
  -> LangGraphClient
  -> Python Agent Engine /analyze
  -> ROUTER
  -> SCHEMA
  -> SEMANTIC_RESOLVE   # LLM 只做语义匹配（指标/维度/过滤/时间）
  -> SQL_SYNTHESIZE     # 确定性合成 SQL（同意图同 SQL）
  -> SQL_HARD_GUARD
  -> SQL_EXECUTE
  -> SQL_VALIDATE
  -> SQL_SOFT_DQ
  -> ANSWER
  -> AnalysisReport
  （语义解析失败/覆盖不到时降级 SQL_GENERATE raw SQL）
```

高风险 SQL 会进入 `WAITING_APPROVAL` 状态，由 Spring Boot 审批接口恢复执行。

## 技术栈

| 层级 | 技术 |
|---|---|
| 平台层 | Spring Boot, MySQL, JSqlParser |
| Agent 引擎层 | Python, FastAPI, LangGraph（StateGraph + interrupt + SQLite checkpoint）, httpx |
| LLM 接入 | OpenAI-compatible API, DeepSeek-compatible API |
| 测试评测 | JUnit, pytest, ruff, eval harness（golden_spec/FakeLLM 回放/A-B） |

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
.\.venv\Scripts\python.exe -m app.eval.runner --llm mock --platform mock
```

## 核心文档

- [docs/ChatBI主链路开发设计.md](docs/ChatBI主链路开发设计.md)
- [docs/ChatBI真实联调手册.md](docs/ChatBI真实联调手册.md)
- [docs/服务接口契约.md](docs/服务接口契约.md)
- [docs/开发规范.md](docs/开发规范.md)
- [docs/Agent编排与架构设计.md](docs/Agent编排与架构设计.md)
- [agent-engine/README.md](agent-engine/README.md)

## 当前边界

- 只有 ChatBI / Text2SQL 一条主线（`graphMode=chatbi`）；全量图（RAG/归因/DBQA）已下线。
- Python 引擎不直接访问数据库，所有确定性平台能力必须通过 Spring Boot 内部接口完成。
- 演进方向：LangGraph 迁移、语义解析 + 确定性合成、评测 harness（见 OpenSpec changes）。
- 每个最小功能点独立提交，提交前至少运行相关 Java/Python 测试。
