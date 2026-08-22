# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-` | metric_recall: `topk`
- 时间: 2026-08-22 12:04:51

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 61/61 |
| 端到端成功率 | 98.36% | 60/61 |
| 口径核心正确率 (L1) | 73.47% | 36/49 |
| 严格全字段正确率 (L2) | 51.02% | 25/49 |
| 平均字段匹配率 (L3) | 85.37% | judged=49 |
| 自动修复成功率 | 100.00% | 1 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 37.70% | 23/61（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/61 |
| 记忆注入率（memory_inject） | 0.00% | 0/61 |
| 指标召回回退率 | 96.72% | 59/61 |
| Planner 调用率 | 0.00% | 0/61 |
| 规划 legacy fallback | 75.41% | 46/61 |
| 规划来源 | - | {'LEGACY_FALLBACK': 46, 'NONE': 15} |
| Planner 可归因成本 | - | prompt chars=0 / latency=0ms / retry=0 |
| 语义 User Prompt 字符数 | 561 avg | total=33120 / p50=561 / p95=566 / N=59 |
| 结果正确率（R1，可断言口径） | 100.00% | 21/21（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 0 | 命中均值 0 / 未命中均值 0 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 16853ms / 41472ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 91.84% |
| metrics | 73.47% |
| dimensions | 93.88% |
| time_range | 75.51% |
| filters | 95.92% |
| ordering | 81.63% |

## 固定子集回归口径

| Subset | E2E | L1 | L2 | Prompt chars avg | Fallback |
|---|---:|---:|---:|---:|---:|
| all | 60/61 | 36/49 | 25/49 | 561 | 59/61 |
| existing_57 | 56/57 | 32/45 | 21/45 | 561 | 55/57 |
| added_4 | 4/4 | 4/4 | 4/4 | 564 | 4/4 |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 20300ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 12392ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 15818ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 10507ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 15536ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 16853ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 20222ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11485ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 17354ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 12147ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 14687ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 19525ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10313ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 12086ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | semantic | 0 | 16412ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | semantic | 0 | 41472ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | semantic | 0 | 25765ms | final report missing expected keywords |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 20126ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 67861ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 32168ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 22086ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 17015ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 16109ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 9513ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 10482ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 15612ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 15476ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 17007ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 14829ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 24634ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 18061ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 11424ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 12042ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 16322ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 7541ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 21851ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 12098ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 11926ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 8352ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10329ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 20668ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 19210ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 9250ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | fallback | 0 | 27556ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 58318ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 19745ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 10804ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | fallback | 0 | 19506ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | fallback | 0 | 25749ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | fallback | 0 | 38489ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | fallback | 0 | 35059ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | fallback | 0 | 20753ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | fallback | 1 | 108210ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | fallback | 0 | 25143ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | fallback | 0 | 41089ms | PASS |
| n38_metric_filter_gt | text2sql | PASS | SUCCESS | semantic | 0 | 18053ms | PASS |
| n39_metric_filter_gte | text2sql | PASS | SUCCESS | semantic | 0 | 18677ms | PASS |
| n40_metric_filter_lt | text2sql | PASS | SUCCESS | semantic | 0 | 12884ms | PASS |
| n41_metric_filter_lte | text2sql | PASS | SUCCESS | semantic | 0 | 13145ms | PASS |
