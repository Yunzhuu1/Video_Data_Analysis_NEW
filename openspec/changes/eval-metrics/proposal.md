## Why

项目已闭环（语义 100%、端到端 96%、门禁/记忆/评测齐全），简历需要**可信的量化指标**。现状：正确性/安全/历史轨迹已有数据，但记忆系统三大价值的两个（直通收益、注入泛化）缺实测，且 token 成本没有计量。本 change 目标是**产出可写进简历的指标报告**，不新增业务功能。

## What Changes

- **Token 计量**：`LLMClient._call` 记录 OpenAI 兼容响应的 `usage`（prompt/completion/total）到模块级 `TokenMeter` 单例；eval runner 每 case 前后快照归因 token 消耗，报告展示每 case + 聚合 token。
- **同义表达问题集（N=20）**：5 类变换分层（指标/维度/时间/过滤排名/对比趋势），每条有已知 golden intent，用于注入收益与冷热启动实验。
- **三个量化实验**：
  1. 直通收益：重复对第一遍（LLM）vs 第二遍（命中）的延迟/token 对比；
  2. 注入收益（长尾泛化）：同义集无记忆 vs 有记忆的解析成功率（L1 口径）对比；
  3. 冷热启动：空记忆 vs 预置记忆跑同义集的成功率/延迟。
- **`docs/metrics-report.md`**：汇总历史轨迹 + 本 change 实测，产出简历可直接引用的指标报告。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `agent-eval`: 新增「量化指标测量」——token 计量、同义集协议（A/B 无记忆 vs 有记忆、冷热启动）、指标报告。

## Impact

- **Python**：`app/clients/token_meter.py`（新增）、`app/clients/llm_client.py`（_call 记录 usage）、`app/eval/runner.py`（token 快照归因 + 报告）、`app/eval/`（同义集文件、A/B 实验入口）。
- **文档**：`docs/metrics-report.md`（新增）、`docs/开发日志.md`。
- **验证**：Python pytest + ruff；真实评测（--memory on 直通/注入/冷热实验；--memory off 基线）。
- **非目标**：业务功能、向量检索、记忆淘汰、前端。

