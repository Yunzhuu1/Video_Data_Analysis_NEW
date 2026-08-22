# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-22 14:34:58

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 95.08% | 58/61 |
| 口径核心正确率 (L1) | 95.92% | 47/49 |
| 严格全字段正确率 (L2) | 57.14% | 28/49 |
| 平均字段匹配率 (L3) | 90.14% | judged=49 |
| 自动修复成功率 | 0.00% | 0 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 37.70% | 23/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 16.39% | 10/61 |
| 记忆注入率（memory_inject） | 29.51% | 18/61 |
| 指标召回回退率 | 4.92% | 3/61 |
| Planner 调用率 | 39.34% | 24/61 |
| 规划 legacy fallback | 24.59% | 15/61 |
| 规划来源 | - | {'AUTO_POLICY': 1, 'AUTO_SINGLE': 13, 'LEGACY_FALLBACK': 15, 'NONE': 8, 'PLANNER_AGENT': 24} |
| Planner 可归因成本 | - | prompt chars=37169 / latency=71272ms / retry=0 |
| 语义 User Prompt 字符数 | 637 avg | total=31232 / p50=490 / p95=1062 / N=49 |
| 结果正确率（R1，可断言口径） | 92.86% | 26/28（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 0 | 命中均值 0 / 未命中均值 0 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 15036ms / 35201ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.88% |
| metrics | 95.92% |
| dimensions | 95.92% |
| time_range | 67.35% |
| filters | 93.88% |
| ordering | 93.88% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 58/61 | 47/49 | 28/49 | 637 | 3/61 |
| existing_57 | 56/57 | 43/45 | 26/45 | 638 | 3/57 |
| added_4 | 2/4 | 4/4 | 2/4 | 634 | 0/4 |

## 交叉诊断：L1 对 + R1 错（value_mismatch）

以下用例语义解析正确（L1 通过）但真实执行结果与 seed 42 真值不符——**解析对但 SQL 错的合成器/生成 bug 信号**：

| Case | 失败详情 |
|---|---|
| n37_video_revenue_rank_trend | order ['content_5', 'content_6', 'content_4', 'content_3', 'content_2'] != ['content_5', 'content_6', 'content_3', 'content_4', 'content_2'] |
| n40_metric_filter_lt | 游戏:missing; 美妆:missing |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 18927ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 10341ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10372ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 10601ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9395ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 9425ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 21416ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 27859ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 35201ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 7274ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | fallback | 0 | 12630ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 18583ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | memory | 0 | 10335ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | memory | 0 | 18059ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | memory | 0 | 15638ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | memory | 0 | 27665ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | memory | 0 | 15602ms | final report missing expected keywords |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 11468ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 22963ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 73672ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 19898ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 34465ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | memory | 0 | 8810ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 15481ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 11144ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 18274ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 17562ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 19510ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 22133ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 21242ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 9957ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | memory | 0 | 36977ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 7147ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 28970ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15531ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15036ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | memory | 0 | 6436ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 15749ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 21440ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 11829ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 14499ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 29352ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 62040ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 14633ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 16520ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 11873ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 6153ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 10185ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 9430ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 6321ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 5851ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 17991ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 16848ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9220ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9673ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 14275ms | PASS |
| n39_metric_filter_gte | text2sql | FAIL | SUCCESS | memory | 0 | 10694ms | generated SQL missing expected fragments |
| n40_metric_filter_lt | text2sql | FAIL | SUCCESS | memory | 0 | 26893ms | generated SQL missing expected fragments |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 13580ms | PASS |
