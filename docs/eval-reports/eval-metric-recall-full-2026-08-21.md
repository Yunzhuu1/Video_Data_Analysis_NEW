# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `full`
- 时间: 2026-08-21 15:36:15

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 98.36% | 60/61 |
| 口径核心正确率 (L1) | 95.92% | 47/49 |
| 严格全字段正确率 (L2) | 57.14% | 28/49 |
| 平均字段匹配率 (L3) | 90.82% | judged=49 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 0.00% | 0/61 |
| 语义 User Prompt 字符数 | 1060 avg | total=62561 / p50=1060 / p95=1065 / N=59 |
| 结果正确率（R1，可断言口径） | 100.00% | 29/29（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 221103 | 命中均值 0 / 未命中均值 3625 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 12564ms / 27600ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 95.92% |
| metrics | 95.92% |
| dimensions | 97.96% |
| time_range | 67.35% |
| filters | 100.00% |
| ordering | 87.76% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 60/61 | 47/49 | 28/49 | 1060 | 0/61 |
| existing_57 | 56/57 | 43/45 | 24/45 | 1060 | 0/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 1062 | 0/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 8541ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 14984ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11750ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 11203ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 18473ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 6546ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 11063ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11873ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14082ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 13261ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 12551ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10988ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 14303ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 9771ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 33144ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 16588ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 9709ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 18094ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 26471ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 27600ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 18758ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 31315ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 6477ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 12037ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 25660ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 10623ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 12248ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 20910ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 37627ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11559ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11515ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 16531ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 10993ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 10988ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15191ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 13513ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 20217ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10669ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 15262ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 8226ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13384ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 18053ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 22168ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 12036ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 12082ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 8643ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 8354ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 5989ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 15114ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 8700ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 11433ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12564ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13408ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13538ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 22699ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 16907ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 25126ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 13309ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 11391ms | PASS |
