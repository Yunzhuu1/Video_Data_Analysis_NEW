# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-14 11:42:36

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 23/23 |
| 端到端成功率 | 73.91% | 17/23 |
| 口径核心正确率 (L1) | 100.00% | 13/13 |
| 严格全字段正确率 (L2) | 53.85% | 7/13 |
| 平均字段匹配率 (L3) | 91.03% | judged=13 |
| 自动修复成功率 | 0.00% | 0 cases retried |
| 高风险拦截率 | 66.67% | 3 cases |
| 延迟 p50 / p95 | 13308ms / 29576ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 61.54% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 84.62% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 26515ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 5169ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 11936ms | PASS |
| c04_completion_rate | metric | FAIL | WAITING_APPROVAL | semantic | 0 | 2707ms | final report missing required fields |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 8328ms | PASS |
| c06_top10_videos | text2sql | FAIL | WAITING_APPROVAL | semantic | 0 | 10460ms | final report missing required fields |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 26637ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 12193ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 22818ms | PASS |
| c10_engagement_rate | metric | FAIL | WAITING_APPROVAL | semantic | 0 | 2817ms | final report missing required fields |
| c11_shares_total | text2sql | FAIL | SUCCESS | semantic | 0 | 7222ms | final report missing required fields |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 14460ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 22918ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | semantic | 0 | 12691ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | semantic | 0 | 29831ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | semantic | 0 | 27277ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | semantic | 0 | 8633ms | final report missing expected keywords |
| c18_detail_playback | risk | FAIL | SUCCESS | semantic | 0 | 33779ms | status=SUCCESS expected=WAITING_APPROVAL |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 26084ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 19242ms | PASS |
| c21_open_reason | open | PASS | WAITING_APPROVAL | semantic | 0 | 22260ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 13227ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 13308ms | PASS |
