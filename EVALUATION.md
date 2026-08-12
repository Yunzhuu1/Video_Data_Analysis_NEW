# ChatBI 评测体系

> 评测只覆盖 ChatBI 主链路（语义解析 → 确定性合成 → 护栏 → 执行 → DQ → 回答）。
> 原则：**指标先实测、后定标**；本文不再写拍脑袋的"目标值"。

## 评测分层

| 层级 | 目标 | 运行方式 |
|---|---|---|
| 单元测试 | 比较器 / 合成器 / FakeLLM 行为 | `pytest` |
| Mock Eval | 不依赖 LLM/MySQL，验证图逻辑与降级路径 | `python -m app.eval.runner --mode mock` |
| Replay Eval | FakeLLM 回放真实录制的响应，CI 可复现 | `python -m app.eval.runner --mode replay --cassette cassettes/xxx.json` |
| Real Eval | 真实 LLM + Spring Boot + MySQL 出数字 | `python -m app.eval.runner --mode real` |

**回放 ≠ 质量测量**：replay 用于回归（图逻辑正确性、可复现）；真实数字来自 `--mode real`（需 API key 与 MySQL）。真实跑一次后录制 cassette，之后 CI 用 replay 回归。

## 核心指标（计算口径）

| 指标 | 定义 | 说明 |
|---|---|---|
| 端到端成功率 | 产出合法 `AnalysisReport`（summary/sql/metrics 非空）的用例占比 | 所有用例 |
| 口径核心正确率 (L1) | `metrics` 解析正确的可判定用例占比 | 有 `golden_spec` 的用例；**简历主打数字** |
| 严格全字段正确率 (L2) | intent/metrics/dimensions/time_range/filters/ordering 全部匹配的占比 | 兜底 |
| 平均字段匹配率 (L3) | Σ(正确字段数/必需字段数)/用例数 | 迭代梯度信号 |
| 分项正确率 (L4) | 每个字段单独报（intent/metrics/dimensions/time_range/filters/ordering） | 定位短板 |
| 自动修复成功率 | 首次失败后 ≤3 次重试内成功的用例占比 | retry_count>0 的用例 |
| 高风险拦截率 | 高风险 SQL 进入 WAITING_APPROVAL 的占比 | risk 类用例，目标 100% |
| 延迟 p50/p95 | 单用例耗时中位数/95 分位 | mock 为 0，real/replay 有值 |

## golden_spec 与比较规则

- 每个可判定用例标注 `golden_spec`（与 agent 的 `ResolvedIntent` 同构：intent/metrics/dimensions/time_range/filters/ordering）。
- 开放性/歧义用例不设 `golden_spec`，只统计端到端成功率。
- 比较前归一化：指标别名→代码、维度无序集合、时间区间按固定 `eval_date` 展开、过滤三元组。
- 时间容差：起点终点相同 + 长度差 ≤ 1 天 + 粒度一致；`none` vs 有区间算错（多约束/漏约束）。
- 指标选错 = 整个答案错 → 核心口径正确率硬门槛。

## 用例集

`agent-engine/app/eval/cases.yaml`（21 条：13 条可判定 golden + 2 条风险 + 2 条重试 + 1 条 DQ warning + 1 条结构 + 2 条开放）。

## 运行命令

```bash
cd agent-engine
.venv/bin/python -m pytest tests
.venv/bin/python -m ruff check app tests
.venv/bin/python -m app.eval.runner --mode mock                 # CI 回归
.venv/bin/python -m app.eval.runner --mode replay --cassette cassettes/xxx.json
.venv/bin/python -m app.eval.runner --mode real                  # 需要 API key + MySQL
.venv/bin/python -m app.eval.runner --compare a.json b.json      # A/B 对比
```

报告输出 `docs/eval-report.md` 与 `docs/eval-report.json`。

## 失败处理规范

评测失败时不要调低用例难度，先定位失败层级：解析 → 合成 → 护栏 → 执行 → DQ → 回答。只有业务口径变化时才修改用例本身。
