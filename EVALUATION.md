# ChatBI 评测体系

本文档定义当前项目的评测口径。评测优先覆盖 ChatBI / Text2SQL 主链路，RAG、归因、DBQA 暂不作为当前主线通过标准。

## 评测目标

评测需要回答四个问题：

1. 自然语言问题能否生成可执行 SQL。
2. SQL 是否通过平台层硬校验与安全约束。
3. 执行结果是否能生成结构化 `AnalysisReport`。
4. 高风险 SQL、执行失败、DQ warning 是否能被正确处理。

## 评测分层

| 层级 | 目标 | 运行方式 |
|---|---|---|
| 单元测试 | 校验 Java/Python 关键服务行为 | `mvn test`, `pytest` |
| Mock Eval | 不依赖真实 Spring Boot 和数据库，验证 Agent 图逻辑 | `python -m app.eval.runner --mode mock` |
| Real Eval | 通过 Spring Boot 入口完成真实联调 | `python -m app.eval.runner --mode real` |
| 人工验收 | 检查 SQL 语义、图表、回答质量 | 按用例人工复核 |

## 核心指标

| 指标 | 定义 | 合格线 |
|---|---|---|
| SQL 生成成功率 | 成功生成非空 SELECT SQL 的 case 占比 | >= 90% |
| 硬校验通过率 | 无需人工审批且通过 `/internal/sql/validate` 的 case 占比 | >= 80% |
| 自动修复成功率 | 首次失败后经反馈重试成功的 case 占比 | >= 60% |
| 执行成功率 | SQL Gateway 成功返回结果的 case 占比 | >= 80% |
| 报告结构正确率 | 返回 JSON 可映射为 `AnalysisReport` 的 case 占比 | >= 95% |
| 高风险拦截率 | 明细大表、无限制查询等风险 SQL 被拦截或审批的比例 | 100% |

## 推荐评测用例

| 编号 | 问题 | 类型 | 重点 |
|---|---|---|---|
| C01 | 分析各分类播放量趋势 | 趋势分析 | GROUP BY、图表 |
| C02 | 统计各分类总播放量 | 聚合查询 | SUM、排序 |
| C03 | 最近 7 天每天播放量是多少 | 时间序列 | 日期过滤 |
| C04 | 完播率是多少 | 指标查询 | 指标公式 |
| C05 | 美食类视频总播放量是多少 | 条件过滤 | WHERE |
| C06 | 播放量最高的 10 个视频 | TopN | ORDER BY、LIMIT |
| C07 | 查询所有播放明细 | 高风险查询 | 必须拦截或审批 |
| C08 | 不加时间范围查询用户行为明细 | 高风险查询 | 必须等待审批 |
| C09 | 对比美食和游戏分类的播放趋势 | 多分类对比 | GROUP BY 多维 |
| C10 | 分析各分类互动率 | 指标计算 | 派生指标 |

后续可扩展到 20 条以上 case，并在 `agent-engine/app/eval/cases.yaml` 中维护。

## 运行命令

### Java 测试

```powershell
mvn test
```

### Python 测试

```powershell
cd agent-engine
.\.venv\Scripts\python.exe -m pytest tests
.\.venv\Scripts\python.exe -m ruff check app tests
```

### Mock Eval

```powershell
cd agent-engine
.\.venv\Scripts\python.exe -m app.eval.runner --mode mock
```

### Real Eval

运行前需要启动 MySQL、Redis、Spring Boot 和 Agent Engine，并设置 `PLATFORM_CALLS_ENABLED=true`。

```powershell
cd agent-engine
.\.venv\Scripts\python.exe -m app.eval.runner --mode real
```

## 真实链路 Smoke Test

```powershell
$message = [uri]::EscapeDataString('分析各分类播放量趋势')
$url = "http://127.0.0.1:8080/api/agent/analyze?userId=demo&message=$message&nocache=true&engine=langgraph"
Invoke-RestMethod -Uri $url
```

验收点：

- Spring Boot 返回 HTTP 200。
- 返回体可以反序列化为 `AnalysisReport`。
- `summary` 非空。
- `sql` 非空且为 SELECT。
- `charts` 与查询结果字段对应。
- 如果存在 DQ warning，最终结果中必须保留 warning。

## 报告输出

Eval runner 的输出应写入：

```text
docs/eval-report.md
```

报告至少包含：

- 执行时间。
- 运行模式：mock / real。
- case 总数、通过数、失败数。
- 每个 case 的问题、状态、耗时、失败原因。
- 聚合指标。

## 失败处理规范

评测失败时不要直接调低用例难度，优先定位失败层级：

| 失败位置 | 优先排查 |
|---|---|
| SQL 为空 | Prompt、LLM 配置、schemaContext |
| SQL 硬校验失败 | Java `SqlValidationService` 与 Python retryable 分类 |
| SQL 执行失败 | 表字段、方言、平台接口协议 |
| DQ warning 丢失 | `SQL_SOFT_DQ` 到 `ANSWER` 的状态传递 |
| DTO 映射失败 | Java `AnalysisReport` 字段兼容性 |

只有当业务口径变化时，才修改评测用例本身。
