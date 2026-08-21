# Metric Recall 真实 LLM A/B 摘要

> 运行日期：2026-08-21；模型：`deepseek-v4-flash`（temperature=0）；协议：`--llm real --platform mock --memory off`；embedding：关闭。  
> 样本：端到端 N=61；含 `golden_spec` 的语义判定 N=49；既有回归子集 N=57（其中 judged=45）。真实 LLM 各跑一轮，正确率变化仅作方向性观察。

## 1. 离线召回门禁（确定性）

| 指标 | 结果 |
|---|---:|
| `recall@configured_k`（K=5） | 49/49 |
| `strict_recall@effective_k` | 49/49 |
| effective recall | 49/49 |
| 多指标完整召回 | 2/2 |
| pinned 扩容次数 | 0 |
| judged fallback | 1/49（`n25_longtail`，`no_reliable_signal`） |

`effective_k=max(configured_k,pinned_count)`；本轮没有发生 pinned>K，因此两种 Recall 数值相同，但报告仍保留独立口径。

## 2. 真实 LLM full / top-k 对照

| 指标 | full catalog | top-k | 变化 |
|---|---:|---:|---:|
| Prompt chars（均值） | 1060 | 497 | **-53.16%** |
| Prompt chars（总计，N=59 实际语义调用） | 62,561 | 29,306 | -53.16% |
| Token 总量 | 221,103 | 195,992 | **-11.36%** |
| 端到端 | 60/61 | 61/61 | +1（方向性） |
| L1 | 47/49 | 48/49 | +1（方向性） |
| L2 | 28/49 | 32/49 | +4（方向性） |
| L3 | 90.82% | 92.52% | +1.70pp（方向性） |
| R1 | 29/29 | 29/29 | 不变 |
| ERROR | 0/61 | 0/61 | 不变 |
| p50 / p95 | 12.564s / 27.600s | 12.171s / 25.953s | -0.393s / -1.647s（方向性） |
| recall fallback | 0/61（显式 full，不算 fallback） | 3/61 | `no_reliable_signal` |
| sql_source semantic / fallback / N/A | 54 / 5 / 2 | 53 / 6 / 2 | top-k 多 1 次 raw 降级 |

### 既有 N=57 子集

| 指标 | full | top-k |
|---|---:|---:|
| 端到端 | 56/57 | 57/57 |
| L1（judged=45） | 43/45 | 44/45 |
| L2（judged=45） | 24/45 | 28/45 |
| Prompt chars 均值 | 1060 | 500 |

## 3. 逐例差异审计

- `n19_longtail`（“哪些视频最受欢迎”）：full 选 `total_plays`，top-k 通过审计别名 pinned `engagement_rate`，L1 由错转对；这是本轮唯一 L1 翻转。
- `n25_longtail`：两组都错误；top-k 判定低信号并 full fallback，说明“回退保住 catalog 可见性”不等于 LLM 一定选对指标。
- top-k 的三次回退为 `c19_detail_without_time`、`c22_fact_full_scan_approval`、`n25_longtail`，均是 `no_reliable_signal`；前两条非 golden judged 用例，仍按原安全路径执行。
- `c04/n06/n15` 的 L2 改善来自 `ordering/time_range` 输出形态差异；`c07` 端到端报告字段差异也可能受 AnswerAgent 单轮波动影响，不能归因于召回算法。
- 两组 R1 均为 29/29，说明候选裁剪没有破坏当前可断言查询的 SQL 结果正确性。

## 4. 可辩护结论

1. **确定性结论**：无 embedding 的别名 + 字符 n-gram 召回在 49 条 judged cases 上达到 49/49 的 `strict_recall@effective_k`，并将最终语义 user prompt 字符数减少 53.16%。
2. **成本方向性结论**：单轮真实调用 token 总量减少 11.36%；不能把字符缩减直接等同为 token 等比例缩减。
3. **正确率结论**：本轮 L1 未回退且增加 1 例，但真实 LLM 仅各运行一次，不能宣称统计显著提升；正确率硬门槛依赖离线召回与回归测试。
4. **边界**：低信号自动退回完整 catalog；显式 `full` 与异常 `full_fallback` 分开计数；当前没有使用 embedding，后续 catalog/语言复杂度继续扩大时再评估二阶段语义召回。

