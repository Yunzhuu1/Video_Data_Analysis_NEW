# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-19 13:06:49

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 45/45 |
| 端到端成功率 | 95.56% | 43/45 |
| 口径核心正确率 (L1) | 96.97% | 32/33 |
| 严格全字段正确率 (L2) | 60.61% | 20/33 |
| 平均字段匹配率 (L3) | 91.41% | judged=33 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/45（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/45 |
| 记忆注入率（memory_inject） | 0.00% | 0/45 |
| 结果正确率（R1，可断言口径） | 100.00% | 17/17（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 141251 | 命中均值 0 / 未命中均值 3139 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 12913ms / 38193ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.94% |
| metrics | 96.97% |
| dimensions | 96.97% |
| time_range | 66.67% |
| filters | 100.00% |
| ordering | 93.94% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 11897ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 11857ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9833ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 5588ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10932ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 6423ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 11297ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 13540ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 8272ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 14792ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 11916ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9896ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9947ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | semantic | 0 | 6775ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 17528ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 31846ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 10444ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 5937ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 29303ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 39780ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 20074ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 44643ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 12488ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 12913ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 28517ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 15350ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 13804ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 18311ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 55536ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 16397ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 26441ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 15725ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11839ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 11287ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 11896ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 16860ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 10473ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 26481ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 16527ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 6753ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 14599ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 12937ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 14303ms | PASS |
