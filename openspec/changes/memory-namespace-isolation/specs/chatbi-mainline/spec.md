## ADDED Requirements

### Requirement: 分析请求透传记忆命名空间
`/api/agent/analyze` SHALL 接收可选的 `memoryNamespace` 参数（默认 `"default"`），并经 `LangGraphClient` 透传给 Python `/analyze`，使主链路请求可按 namespace 隔离语义记忆。

#### Scenario: 默认命名空间
- **WHEN** 客户端调用 `/api/agent/analyze` 且不传 `memoryNamespace`
- **THEN** 引擎记忆读写使用 `"default"` namespace

#### Scenario: 指定命名空间透传
- **WHEN** 客户端调用 `/api/agent/analyze` 并传 `memoryNamespace=eval-xxx`
- **THEN** Spring 将该参数透传给 Python `/analyze`，引擎按该 namespace 读写记忆
