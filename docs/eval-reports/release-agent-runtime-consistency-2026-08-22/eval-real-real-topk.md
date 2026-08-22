# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-22 14:51:42

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 98.36% | 60/61 |
| 口径核心正确率 (L1) | 95.92% | 47/49 |
| 严格全字段正确率 (L2) | 63.27% | 31/49 |
| 平均字段匹配率 (L3) | 90.14% | judged=49 |
| 自动修复成功率 | 0.00% | 0 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 39.34% | 24/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 4.92% | 3/61 |
| Planner 调用率 | 37.70% | 23/61 |
| 规划 legacy fallback | 26.23% | 16/61 |
| 规划来源 | - | {'AUTO_SINGLE': 14, 'LEGACY_FALLBACK': 16, 'NONE': 8, 'PLANNER_AGENT': 23} |
| Planner 可归因成本 | - | prompt chars=35597 / latency=63724ms / retry=0 |
| 语义 User Prompt 字符数 | 497 avg | total=29306 / p50=459 / p95=568 / N=59 |
| 结果正确率（R1，可断言口径） | 96.55% | 28/29（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 0 | 命中均值 0 / 未命中均值 0 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 13055ms / 29086ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.88% |
| metrics | 95.92% |
| dimensions | 97.96% |
| time_range | 65.31% |
| filters | 97.96% |
| ordering | 89.80% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 60/61 | 47/49 | 31/49 | 497 | 3/61 |
| existing_57 | 56/57 | 43/45 | 27/45 | 500 | 3/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 458 | 0/4 |

## 交叉诊断：L1 对 + R1 错（value_mismatch）

以下用例语义解析正确（L1 通过）但真实执行结果与 seed 42 真值不符——**解析对但 SQL 错的合成器/生成 bug 信号**：

| Case | 失败详情 |
|---|---|
| n37_video_revenue_rank_trend | order ['content_5', 'content_6', 'content_4', 'content_3', 'content_2'] != ['content_5', 'content_6', 'content_3', 'content_4', 'content_2'] |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 19428ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 12046ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9968ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 5380ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 7747ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 5960ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 11160ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 14371ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 21471ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 4864ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 8012ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13055ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11486ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 14536ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | semantic | 0 | 29086ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | semantic | 0 | 24784ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | semantic | 0 | 17004ms | final report missing expected keywords |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 17998ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 25883ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 34040ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 26690ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 13483ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 12243ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 11055ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 8463ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 12796ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 13682ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 13003ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 21430ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 14102ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 21467ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 13728ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 16021ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 8534ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | fallback | 0 | 77462ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15960ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 11084ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 29805ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13807ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 6609ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 14450ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 28336ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 9107ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 8825ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 23514ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 9346ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 4871ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 4915ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 6732ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 10195ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 5254ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 15700ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 16990ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 5624ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9843ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 15423ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 14330ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 9919ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 13121ms | PASS |
