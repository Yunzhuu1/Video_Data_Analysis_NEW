# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-22 10:19:39

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 98.36% | 60/61 |
| 口径核心正确率 (L1) | 100.00% | 49/49 |
| 严格全字段正确率 (L2) | 61.22% | 30/49 |
| 平均字段匹配率 (L3) | 91.50% | judged=49 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 4.92% | 3/61 |
| Planner 调用率 | 39.34% | 24/61 |
| 规划 legacy fallback | 26.23% | 16/61 |
| 规划来源 | - | {'AUTO_POLICY': 1, 'AUTO_SINGLE': 14, 'LEGACY_FALLBACK': 16, 'NONE': 6, 'PLANNER_AGENT': 24} |
| Planner 可归因成本 | - | prompt chars=36601 / latency=73056ms / retry=0 |
| 语义 User Prompt 字符数 | 497 avg | total=29306 / p50=459 / p95=568 / N=59 |
| 结果正确率（R1，可断言口径） | 100.00% | 29/29（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 228741 | 命中均值 0 / 未命中均值 3750 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 14645ms / 30846ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 95.92% |
| metrics | 100.00% |
| dimensions | 100.00% |
| time_range | 67.35% |
| filters | 100.00% |
| ordering | 85.71% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 60/61 | 49/49 | 30/49 | 497 | 3/61 |
| existing_57 | 56/57 | 45/45 | 26/45 | 500 | 3/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 458 | 0/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12959ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 10312ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 13450ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 10750ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 13793ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 11714ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 14585ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 22729ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13593ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 23559ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 14641ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9254ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 25842ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 16787ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 23871ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 18776ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 16675ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 28646ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 40693ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 59298ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 27680ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 39302ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 15031ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 14438ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 29018ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 14290ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 17377ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 22518ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 18878ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 14536ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 14401ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 27878ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 13738ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 9946ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 9915ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 14645ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 26834ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 25093ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 17515ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10579ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 20628ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13981ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 30846ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 12400ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 13397ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 11309ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 14039ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 13364ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 7378ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 8680ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 20633ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14798ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13454ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 17436ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 15427ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 19566ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 21346ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 13965ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 18022ms | PASS |
