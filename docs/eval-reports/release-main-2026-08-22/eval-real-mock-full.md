# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `full`
- 时间: 2026-08-22 10:34:47

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 96.72% | 59/61 |
| 口径核心正确率 (L1) | 95.92% | 47/49 |
| 严格全字段正确率 (L2) | 63.27% | 31/49 |
| 平均字段匹配率 (L3) | 91.50% | judged=49 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 0.00% | 0/61 |
| Planner 调用率 | 39.34% | 24/61 |
| 规划 legacy fallback | 29.51% | 18/61 |
| 规划来源 | - | {'AUTO_POLICY': 1, 'AUTO_SINGLE': 14, 'LEGACY_FALLBACK': 18, 'NONE': 4, 'PLANNER_AGENT': 24} |
| Planner 可归因成本 | - | prompt chars=36230 / latency=74417ms / retry=0 |
| 语义 User Prompt 字符数 | 1060 avg | total=62561 / p50=1060 / p95=1065 / N=59 |
| 结果正确率（R1，可断言口径） | 100.00% | 29/29（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 224297 | 命中均值 0 / 未命中均值 3677 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 13556ms / 26164ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 95.92% |
| metrics | 95.92% |
| dimensions | 100.00% |
| time_range | 65.31% |
| filters | 100.00% |
| ordering | 91.84% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 59/61 | 47/49 | 31/49 | 1060 | 0/61 |
| existing_57 | 55/57 | 43/45 | 27/45 | 1060 | 0/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 1062 | 0/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12233ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 11629ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 13074ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 6851ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 14631ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 8292ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 13556ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 21123ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12428ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 11836ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 9241ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 11117ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10860ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | semantic | 0 | 20136ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 17133ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 21614ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 10499ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 4968ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 16454ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | semantic | 0 | 14795ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 15430ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 31119ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 11817ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 9391ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 10648ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 13617ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 17294ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 20059ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 24926ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11306ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 9788ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 12288ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 14152ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15756ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 28295ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 13601ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 8346ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 20948ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 19143ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 8170ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 23403ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 21776ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 16513ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 5971ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 13155ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 14054ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 12026ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 8552ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 10236ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 15288ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 9222ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 13795ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10702ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 26164ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 11097ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 26720ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 18963ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 17664ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 16765ms | PASS |
