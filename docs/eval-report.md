# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-13 16:14:42

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 21/21 |
| 端到端成功率 | 47.62% | 10/21 |
| 口径核心正确率 (L1) | 100.00% | 13/13 |
| 严格全字段正确率 (L2) | 61.54% | 8/13 |
| 平均字段匹配率 (L3) | 92.31% | judged=13 |
| 自动修复成功率 | 12.50% | 8 cases retried |
| 高风险拦截率 | 0.00% | 2 cases |
| 延迟 p50 / p95 | 30238ms / 77218ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 61.54% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 92.31% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 24491ms | PASS |
| c02_category_total | text2sql | FAIL | SUCCESS | fallback | 3 | 76840ms | final report missing required fields |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 18598ms | PASS |
| c04_completion_rate | metric | FAIL | WAITING_APPROVAL | semantic | 0 | 6284ms | final report missing required fields |
| c05_food_plays | text2sql | FAIL | WAITING_APPROVAL | fallback | 1 | 45977ms | final report missing required fields |
| c06_top10_videos | text2sql | PASS | SUCCESS | fallback | 2 | 115190ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | semantic | 0 | 19000ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 5362ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 31380ms | PASS |
| c10_engagement_rate | metric | FAIL | WAITING_APPROVAL | semantic | 0 | 2853ms | final report missing required fields |
| c11_shares_total | text2sql | FAIL | SUCCESS | fallback | 3 | 72948ms | final report missing required fields |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 22010ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 20044ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | fallback | 3 | 59675ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | FAIL | SUCCESS | semantic | 0 | 30238ms | sql_retry_count=0 expected=1 |
| c16_dq_retry | dq | FAIL | SUCCESS | semantic | 0 | 15180ms | sql_retry_count=0 expected=1 |
| c17_dq_warning | dq | FAIL | SUCCESS | fallback | 3 | 62830ms | final report missing expected keywords |
| c18_detail_playback | risk | FAIL | SUCCESS | fallback | 2 | 67896ms | status=SUCCESS expected=WAITING_APPROVAL |
| c19_detail_without_time | risk | FAIL | SUCCESS | fallback | 1 | 77218ms | status=SUCCESS expected=WAITING_APPROVAL |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 46241ms | PASS |
| c21_open_reason | open | PASS | WAITING_APPROVAL | semantic | 0 | 16089ms | PASS |
