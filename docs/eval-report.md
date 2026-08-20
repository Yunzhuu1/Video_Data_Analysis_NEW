# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-20 17:26:14

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 57/57 |
| 端到端成功率 | 98.25% | 56/57 |
| 口径核心正确率 (L1) | 97.78% | 44/45 |
| 严格全字段正确率 (L2) | 55.56% | 25/45 |
| 平均字段匹配率 (L3) | 90.74% | judged=45 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/57（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/57 |
| 记忆注入率（memory_inject） | 0.00% | 0/57 |
| 结果正确率（R1，可断言口径） | 96.00% | 24/25（真实 MySQL 独立执行，seed 42 真值） |
| Token 总消耗 | 201567 | 命中均值 0 / 未命中均值 3536 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 14959ms / 29507ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 93.33% |
| metrics | 97.78% |
| dimensions | 97.78% |
| time_range | 64.44% |
| filters | 100.00% |
| ordering | 91.11% |

## 交叉诊断：L1 对 + R1 错（value_mismatch）

以下用例语义解析正确（L1 通过）但真实执行结果与 seed 42 真值不符——**解析对但 SQL 错的合成器/生成 bug 信号**：

| Case | 失败详情 |
|---|---|
| n16_cross_table | content_1:missing; content_2:missing; content_3:missing; content_4:missing; content_5:missing; content_6:missing |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 6997ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 12325ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 9958ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 20774ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 14959ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 12460ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14824ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10736ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 16072ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 18728ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 12940ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14165ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 17564ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | semantic | 0 | 19734ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 17826ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 19861ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 7600ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 15563ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 22707ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 31713ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 17239ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 28955ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 11623ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| n01_multi_metric | text2sql | PASS | SUCCESS | semantic | 0 | 6407ms | PASS |
| n02_multi_metric | text2sql | PASS | SUCCESS | fallback | 0 | 45469ms | PASS |
| n04_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 12450ms | PASS |
| n05_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 15115ms | PASS |
| n06_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 14973ms | PASS |
| n07_multi_filter | text2sql | PASS | SUCCESS | semantic | 0 | 33454ms | PASS |
| n09_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 13195ms | PASS |
| n10_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 21158ms | PASS |
| n11_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 10218ms | PASS |
| n12_ranked_time | text2sql | PASS | SUCCESS | semantic | 0 | 16357ms | PASS |
| n14_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15875ms | PASS |
| n15_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 15656ms | PASS |
| n16_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 10607ms | PASS |
| n17_cross_table | text2sql | PASS | SUCCESS | semantic | 0 | 17666ms | PASS |
| n19_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 24135ms | PASS |
| n20_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 14458ms | PASS |
| n21_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 18750ms | PASS |
| n22_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 19659ms | PASS |
| n23_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 13094ms | PASS |
| n25_longtail | text2sql | PASS | SUCCESS | semantic | 0 | 10961ms | PASS |
| n26_comment_rate | text2sql | PASS | SUCCESS | semantic | 0 | 25608ms | PASS |
| n27_like_rate | text2sql | PASS | SUCCESS | semantic | 0 | 12245ms | PASS |
| n28_share_rate | text2sql | PASS | SUCCESS | semantic | 0 | 17222ms | PASS |
| n29_avg_completion | text2sql | PASS | SUCCESS | semantic | 0 | 9415ms | PASS |
| n30_creator_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 18133ms | PASS |
| n31_video_revenue | text2sql | PASS | SUCCESS | semantic | 0 | 20676ms | PASS |
| n32_active_creator | text2sql | PASS | SUCCESS | semantic | 0 | 7951ms | PASS |
| n33_dau | text2sql | PASS | SUCCESS | semantic | 0 | 11506ms | PASS |
| n34_creator_revenue_trend | text2sql | PASS | SUCCESS | semantic | 0 | 7441ms | PASS |
| n35_comment_rate_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9048ms | PASS |
| n36_dau_trend | text2sql | PASS | SUCCESS | semantic | 0 | 10055ms | PASS |
| n37_video_revenue_rank_trend | text2sql | PASS | SUCCESS | semantic | 0 | 8054ms | PASS |
