# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-21 15:49:54

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 100.00% | 61/61 |
| 口径核心正确率 (L1) | 97.96% | 48/49 |
| 严格全字段正确率 (L2) | 65.31% | 32/49 |
| 平均字段匹配率 (L3) | 92.52% | judged=49 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 4.92% | 3/61 |
| 语义 User Prompt 字符数 | 497 avg | total=29306 / p50=459 / p95=568 / N=59 |
| 结果正确率（R1，可断言口径） | 100.00% | 29/29（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 195992 | 命中均值 0 / 未命中均值 3213 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 12171ms / 25953ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 95.92% |
| metrics | 97.96% |
| dimensions | 97.96% |
| time_range | 67.35% |
| filters | 100.00% |
| ordering | 95.92% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 61/61 | 48/49 | 32/49 | 497 | 3/61 |
| existing_57 | 57/57 | 44/45 | 28/45 | 500 | 3/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 458 | 0/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9635ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 14733ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 19063ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 5108ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 16470ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 8972ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12064ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 15166ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10018ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 10593ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 13144ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 5933ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11231ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 8832ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 12749ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 15952ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 8973ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 31381ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 16480ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 29068ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 11186ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 25953ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 9615ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 12789ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 19454ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 9960ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 8993ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 12171ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 12364ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 12342ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 13863ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 16992ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 8583ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 10254ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 19212ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 25360ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 11859ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 31562ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13976ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 9329ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 12834ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 8751ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 9174ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 6871ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 11970ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 10821ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 5753ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 12925ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 13619ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 8971ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 10954ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 16267ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12593ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 8035ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 18851ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 19672ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 13544ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 10300ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 13313ms | PASS |
