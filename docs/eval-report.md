# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-17 15:25:21

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 25/25 |
| 端到端成功率 | 96.00% | 24/25 |
| 口径核心正确率 (L1) | 100.00% | 13/13 |
| 严格全字段正确率 (L2) | 100.00% | 13/13 |
| 平均字段匹配率 (L3) | 100.00% | judged=13 |
| 自动修复成功率 | 0.00% | 0 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 16.00% | 4/25（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 16.00% | 4/25 |
| 记忆注入率（memory_inject） | 4.00% | 1/25 |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 13147ms / 29411ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 100.00% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 100.00% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 28206ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 11189ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 23144ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 4440ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 5561ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 18780ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14630ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 15052ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 29712ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 9531ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 8220ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 12631ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 23633ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 11690ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | memory | 0 | 20705ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | memory | 0 | 25196ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | memory | 0 | 3598ms | final report missing expected keywords |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 13147ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 20396ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 45789ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 11679ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 26180ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | memory | 0 | 5070ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
