## ADDED Requirements

### Requirement: 记忆命名空间隔离
语义记忆 SHALL 按 namespace 读写：`/analyze` 请求可携带 `memoryNamespace`（默认 `"default"`），语义解析读路径与写钩子 SHALL 按该 namespace 读写记忆，使 eval/场景记忆与真实记忆互不污染。

#### Scenario: 默认 namespace
- **WHEN** 请求未指定 `memoryNamespace`
- **THEN** 记忆读写使用 `"default"` namespace，与既有行为一致

#### Scenario: 指定 namespace 隔离
- **WHEN** 请求指定 `memoryNamespace=eval-xxx`
- **THEN** 读路径只检索该 namespace 的记忆，写钩子只写入该 namespace；不同 namespace 之间互不可见

#### Scenario: 记忆控制端点
- **WHEN** 内部调用 `POST /internal/memory/seed`（按 namespace 预置）或 `POST /internal/memory/clear`（按 namespace 清空）
- **THEN** 服务器记忆按 namespace 更新，端点需内部 token 校验，且 **seed 拒绝写入 `default` namespace**（生产记忆仅由写钩子沉淀）
