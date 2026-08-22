# DataAgent Evaluation Report

- LLM: `mock` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-22 10:00:46

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 91.80% | 56/61 |
| 口径核心正确率 (L1) | 0.00% | 0/49 |
| 严格全字段正确率 (L2) | 0.00% | 0/49 |
| 平均字段匹配率 (L3) | 0.00% | judged=49 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 4.92% | 3/61 |
| Planner 调用率 | 0.00% | 0/61 |
| 规划 legacy fallback | 0.00% | 0/61 |
| 规划来源 | - | {'NONE': 61} |
| Planner 可归因成本 | - | prompt chars=0 / latency=0ms / retry=0 |
| 语义 User Prompt 字符数 | 497 avg | total=29306 / p50=459 / p95=568 / N=59 |
| 结果正确率（R1，可断言口径） | 0.00% | 0/0（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 0 | 命中均值 0 / 未命中均值 0 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 8ms / 15ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 0.00% |
| metrics | 0.00% |
| dimensions | 0.00% |
| time_range | 0.00% |
| filters | 0.00% |
| ordering | 0.00% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 56/61 | 0/49 | 0/49 | 497 | 3/61 |
| existing_57 | 56/57 | 0/45 | 0/45 | 500 | 3/57 |
| added_4 | 0/4 | 0/4 | 0/4 | 458 | 0/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | fallback | 0 | 18ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | fallback | 0 | 13ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | fallback | 0 | 15ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | fallback | 0 | 21ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | fallback | 0 | 16ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | fallback | 0 | 12ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | fallback | 0 | 12ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | fallback | 0 | 15ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 10ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 13ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 8ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 9ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 11ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | fallback | 0 | 10ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 8ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | fallback | 0 | 13ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 11ms | PASS |
| n02_multi_metric | text2sql | FAIL | SUCCESS | fallback | 0 | 8ms | generated SQL missing expected fragments |
| n04_multi_filter | text2sql | PASS | SUCCESS | fallback | 0 | 10ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | fallback | 0 | 11ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | fallback | 0 | 10ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | fallback | 0 | 10ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | fallback | 0 | 13ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | fallback | 0 | 8ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| n38_metric_filter_gt | text2sql | FAIL | SUCCESS | fallback | 0 | 7ms | generated SQL missing expected fragments |
| n39_metric_filter_gte | text2sql | FAIL | SUCCESS | fallback | 0 | 6ms | generated SQL missing expected fragments |
| n40_metric_filter_lt | text2sql | FAIL | SUCCESS | fallback | 0 | 8ms | generated SQL missing expected fragments |
| n41_metric_filter_lte | text2sql | FAIL | SUCCESS | fallback | 0 | 7ms | generated SQL missing expected fragments |
