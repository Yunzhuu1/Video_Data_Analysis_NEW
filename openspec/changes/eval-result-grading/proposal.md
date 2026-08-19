## Why

评测体系当前只检查**语义层正确率**（L1-L4 = resolvedIntent 与 golden 对比），不检查**最终结果正确性**——"解析对了但 SQL 算错"的 bug（如合成器生成错误 SQL）无法被发现。此前无法做结果断言是因为 mock 平台执行返回写死的假数据（与 SQL 无关）；但真实数据由固定随机种子（seed 42）生成、确定可复现，使 real 平台的结果级评测成为可能且可复现。

## What Changes

- **ResultComparator（按 intent 分层断言）**：aggregate → exact（单行）/ exact_per_key（带维度多行）+容差；trend → 方向断言（单序列/多序列按序列键）；ranking → 集合+顺序断言；detail/歧义 → 不断言。
- **`expected_result` 字段**：给结果可确定的用例标注标准答案——**取真值用独立于合成器的手工 SQL**（直接查库验证，防止把合成器 bug 烘焙进真值），记录 `truth_source`（手工 SQL/查询时间/数据初始化版本）供审计。
- **R1（结果正确率）独立维度**：与 L1-L4 并列报告，端到端口径不变；**L1 错 → R1 标记 N/A**（避免"思路错但结果碰巧对"的假阳性）。
- **平台行为**：mock 平台只评 L1-L4（R1=N/A，假数据无意义）；real 平台（真实 MySQL）评 R1。
- **MVP 范围**：10-15 个结果可确定用例（总量/趋势/排名类），歧义/明细不加。
- **交叉诊断**：报告输出 `L1 对 + R1 错` 用例清单，**仅 `value_mismatch` 类**（执行成功但值不匹配 = 解析对但 SQL 错）；sql_error/exec_error 不计入诊断（防执行噪声污染）。

## Capabilities

### New Capabilities
- `result-grading`: 结果级评测——按 intent 分层的最终结果断言（exact/trend_pattern/top_set）、R1 维度与 L1-L4 并列、真实执行结果可复现验证。

### Modified Capabilities
- `agent-eval`: 「真实指标报告与基线对比」增加 R1 维度；「评测数据覆盖」增加 expected_result 标注场景。

## Impact

- `agent-engine/app/eval/result_comparator.py`（新）：ResultComparator（exact/trend/top_set 断言）。
- `agent-engine/app/eval/cases.yaml`：10-15 个用例加 `expected_result`。
- `agent-engine/app/eval/runner.py`：R1 聚合、报告、交叉诊断。
- 单测 + `docs/metrics-report.md`（R1 维度）+ `docs/开发日志.md`。
- Java：无改动（评测在 Python 侧）。
