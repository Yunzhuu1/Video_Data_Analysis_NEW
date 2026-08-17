# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-17 17:04:07

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 25/25 |
| 端到端成功率 | 96.00% | 24/25 |
| 口径核心正确率 (L1) | 100.00% | 14/14 |
| 严格全字段正确率 (L2) | 92.86% | 13/14 |
| 平均字段匹配率 (L3) | 98.81% | judged=14 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/25（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 16.00% | 4/25 |
| 记忆注入率（memory_inject） | 4.00% | 1/25 |
| Token 总消耗 | 66117 | 命中均值 2160 / 未命中均值 2737 |
| 直通收益（重复对） | token 差均值 -356 / 延迟差均值 -2069ms | 1/1 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 12557ms / 27427ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 100.00% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 92.86% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12557ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 7456ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 8861ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 6979ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 6115ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 8671ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 9365ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 23475ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 6088ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 9414ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 11860ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14260ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 8548ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | fallback | 0 | 15559ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 12328ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 14253ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | fallback | 0 | 17552ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 23539ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 16329ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | semantic | 0 | 28399ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 16287ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 29767ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | memory | 0 | 10659ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | memory | 0 | 12850ms | PASS |
| c25_memory_counterexample | memory | PASS | SUCCESS | semantic | 0 | 13067ms | PASS |
