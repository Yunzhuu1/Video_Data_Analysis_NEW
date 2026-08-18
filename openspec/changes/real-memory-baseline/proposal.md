## Why

default namespace（真实用户路径）的记忆库当前为 **0 条**——`memory.sqlite` 里只有 eval-* namespace 的评测沉淀。现有"命中率 16-20%、命中直通省 ~21% token"全部是**评测场内自命中**（同一评测内先沉淀、后续用例/重复对命中），不能代表真实场景。记忆系统缺"真实生效"的证据链：真实路径命中率、跨请求/跨进程持久化命中、真实直通收益均无数字，这是简历叙事上的空白。

## What Changes

- **新增 `real-session` 评测协议**（真实路径记忆评测）：namespace=`real-<ts>`，按多轮会话执行（首问沉淀 → 二问命中 → 近似问注入），验证跨请求命中与持久化（文件落盘 + 进程重启后命中仍在，强弱双轨分别标注）。
- **口径分离**：报告明确区分「真实路径命中率（real-session 协议）」与「场内自命中（eval 协议）」，杜绝"评测自命中冒充真实命中"的误导。
- **namespace 策略**：real-session 协议默认不写 default（防污染真实记忆库）；提供 `--namespace default` 显式开关，供真实联调时手动开启（写入真实记忆属于联调动作，不进评测协议）。
- **新增真实路径指标**：真实命中率、持久化命中数（强弱双轨）、真实直通 token 省（**方向性，N 小**，解析阶段计量另立 change）、真实同问同答一致率（逐字段口径），写入 metrics-report「真实路径基线」章节。
- **复测**：既有 eval 协议（N=45 基线、重复对、毒化反例）不回退。

## Capabilities

### New Capabilities
- `real-memory-eval`: 真实路径记忆评测协议——real-session 会话执行、场内自命中与真实命中口径分离、namespace 策略、跨请求/跨进程持久化验证。

### Modified Capabilities
- `agent-eval`: 「记忆行为评测」增加"真实路径基线口径"场景——命中率报告须区分场内自命中与真实路径命中，避免口径混用。

## Impact

- `agent-engine/app/eval/runner.py`：real-session 协议、`--namespace` 开关、真实路径指标聚合。
- `agent-engine/app/eval/cases.yaml`：真实会话用例（若需新增）。
- `agent-engine/app/settings.py`：real namespace 相关配置（如默认 `real-` 前缀）。
- `docs/metrics-report.md`：新增「真实路径基线」章节。
- `docs/开发日志.md`：追加本次开发/评测日志。
- specs：`agent-eval`（修改）+ `real-memory-eval`（新增）。
- Java：无改动。
