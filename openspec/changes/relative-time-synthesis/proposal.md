## Why

eval-result-grading（R1）上线的第一个真实战果：**c03「最近7天每天播放量是多少」合成 SQL 无时间过滤**——语义解析出 `time_range: {type: "relative", 7天}`，但合成 SQL 忽略 relative，返回全 31 天（系统"理解对了但答错了"）。实测影响面：**11 个 relative 时间用例中 9 个合成 SQL 无时间过滤**（c03/c13/n04/n09/n10/n11/n22/n23/n25 等，"最近7天/最近30天/最近一周/昨天到今天"全部不生效）。这是"解析对但 SQL 错"的系统性缺口，也是 R1 交叉诊断机制的首个可修复目标。

## What Changes

- **相对时间展开（relative → absolute）**：新增 `time_expand(relative, anchor_date)` 确定性纯函数——`{amount, unit}` + 数据末日锚点 → `{type: "absolute", start, end}`。
- **锚点来源**：nodes 在合成前，若 intent.time_range 为 relative，通过 platform 查询数据表最大日期（real 走 Spring SQL 网关执行 `SELECT MAX(date)`，符合"Python 不直连库"；mock 平台返回固定数据末日 2023-10-31）。seed 42 数据确定性保证锚点稳定、R1 可复现。
- **合成器不变**：展开后 absolute 走既有 BETWEEN 逻辑（已支持）。
- **R1 闭环验证（可断言子集）**：受影响的 11 个 relative 用例中，**R1 可断言子集 = aggregate/trend 用例（c03/c13/n04/n09/n10/n11 等）**取真值并断言；n22/n23/n25 等 detail/歧义用例按 R1 规则 N/A，只验证合成 SQL 含时间过滤（形态验证）。
- **回归**：--memory off N=45 零回退；L1-L4 不受影响（time_range 仍以 golden 的 relative 比对）。

## Capabilities

### New Capabilities
- （无新 capability，属语义层/合成器能力修复）

### Modified Capabilities
- `semantic-resolution`: 「SQL 由确定性合成器生成」增加 relative 时间展开（合成前 relative → absolute，锚点为数据末日）。
- `agent-eval`: 「结果级评测」扩展——relative 时间用例纳入 R1 断言范围（修复后）。

## Impact

- `agent-engine/app/graph/nodes.py`：time_expand 节点（合成前展开 relative）。
- `agent-engine/app/synthesis/time_expand.py`（新）：纯函数。
- `agent-engine/app/eval/runner.py`：R1 扩展到 relative 可断言子集（取真值）；mock anchor 注入；detail/歧义只验 SQL 形态。
- `agent-engine/app/clients/platform_client.py`：`SELECT MAX(date)` 查询支持（或 mock 固定锚点）。
- `agent-engine/app/eval/cases.yaml`：relative 用例标 expected_result。
- 单测 + `docs/metrics-report.md` + `docs/开发日志.md`。
- Java：无改动（查询走现有 SQL 网关）。
