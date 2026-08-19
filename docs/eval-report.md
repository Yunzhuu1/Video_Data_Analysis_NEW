# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-19 11:26:34

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 45/45 |
| 端到端成功率 | 97.78% | 44/45 |
| 口径核心正确率 (L1) | 96.97% | 32/33 |
| 严格全字段正确率 (L2) | 81.82% | 27/33 |
| 平均字段匹配率 (L3) | 95.96% | judged=33 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/45（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/45 |
| 记忆注入率（memory_inject） | 0.00% | 0/45 |
| 结果正确率（R1，可断言口径） | 100.00% | 12/12（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 150076 | 命中均值 0 / 未命中均值 3335 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 15917ms / 34885ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.94% |
| metrics | 96.97% |
| dimensions | 96.97% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 87.88% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10438ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 15477ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9467ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 14072ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 17456ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 13082ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 19889ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 17702ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10898ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 11393ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 26627ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10625ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10042ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 12526ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 17793ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 20569ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 14332ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 20320ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 48307ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 43759ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 35452ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 30215ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 11544ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 16199ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 32619ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 20203ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 15917ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 20159ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 23159ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 9745ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 17290ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 24336ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11335ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 13332ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 7772ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 19565ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 10433ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 17025ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 16918ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 11029ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 9548ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 29179ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10352ms | PASS |
