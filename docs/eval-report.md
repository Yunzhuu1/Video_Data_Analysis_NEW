# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-13 15:08:41

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 21/21 |
| 端到端成功率 | 66.67% | 14/21 |
| 口径核心正确率 (L1) | 100.00% | 13/13 |
| 严格全字段正确率 (L2) | 61.54% | 8/13 |
| 平均字段匹配率 (L3) | 93.59% | judged=13 |
| 自动修复成功率 | 68.42% | 19 cases retried |
| 高风险拦截率 | 0.00% | 2 cases |
| 延迟 p50 / p95 | 40488ms / 91476ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 61.54% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 100.00% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | fallback | 1 | 19808ms | PASS |
| c02_category_total | text2sql | FAIL | SUCCESS | fallback | 3 | 22806ms | final report missing required fields |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | fallback | 2 | 28940ms | PASS |
| c04_completion_rate | metric | FAIL | WAITING_APPROVAL | fallback | 1 | 17285ms | final report missing required fields |
| c05_food_plays | text2sql | PASS | SUCCESS | fallback | 2 | 62500ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | fallback | 3 | 114743ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | fallback | 1 | 57182ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | fallback | 1 | 31380ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | fallback | 1 | 32623ms | PASS |
| c10_engagement_rate | metric | FAIL | WAITING_APPROVAL | fallback | 1 | 17862ms | final report missing required fields |
| c11_shares_total | text2sql | PASS | SUCCESS | fallback | 2 | 78888ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | fallback | 1 | 27163ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | fallback | 2 | 40488ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | fallback | 3 | 62317ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 46601ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 28305ms | PASS |
| c17_dq_warning | dq | FAIL | SUCCESS | fallback | 3 | 68968ms | final report missing expected keywords |
| c18_detail_playback | risk | FAIL | SUCCESS | fallback | 3 | 40234ms | status=SUCCESS expected=WAITING_APPROVAL |
| c19_detail_without_time | risk | FAIL | SUCCESS | fallback | 0 | 47319ms | status=SUCCESS expected=WAITING_APPROVAL |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 91476ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | fallback | 3 | 53102ms | PASS |
