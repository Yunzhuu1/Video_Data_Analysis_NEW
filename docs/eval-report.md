# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-18 18:14:17

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 45/45 |
| 端到端成功率 | 95.56% | 43/45 |
| 口径核心正确率 (L1) | 96.97% | 32/33 |
| 严格全字段正确率 (L2) | 84.85% | 28/33 |
| 平均字段匹配率 (L3) | 96.46% | judged=33 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/45（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/45 |
| 记忆注入率（memory_inject） | 0.00% | 0/45 |
| Token 总消耗 | 149977 | 命中均值 0 / 未命中均值 3333 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 13198ms / 35083ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.94% |
| metrics | 96.97% |
| dimensions | 96.97% |
| time_range | 96.97% |
| filters | 100.00% |
| ordering | 93.94% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10539ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 15627ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10355ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 8482ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 12316ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 10440ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 6934ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 23748ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14397ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 16447ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 9103ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9559ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 12286ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | semantic | 0 | 11416ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 13109ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 10399ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 11193ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 22841ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 33563ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 35099ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 11069ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 72245ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 6788ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 30839ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 35021ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 20919ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 22112ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 13198ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 27524ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 15519ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 15865ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 20652ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 9609ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 13350ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 22097ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 37369ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 19686ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13394ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 12590ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 6947ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10990ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 20458ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 12797ms | PASS |
