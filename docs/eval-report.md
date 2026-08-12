# DataAgent Evaluation Report

- LLM: `mock` | 平台: `mock` | 模型: `deepseek-chat`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-12 16:45:24

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 21/21 |
| 端到端成功率 | 100.00% | 21/21 |
| 口径核心正确率 (L1) | 0.00% | 0/13 |
| 严格全字段正确率 (L2) | 0.00% | 0/13 |
| 平均字段匹配率 (L3) | 0.00% | judged=13 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 2 cases |
| 延迟 p50 / p95 | 6ms / 8ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 0.00% |
| metrics | 0.00% |
| dimensions | 0.00% |
| time_range | 0.00% |
| filters | 0.00% |
| ordering | 0.00% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | fallback | 0 | 9ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | fallback | 0 | 7ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | fallback | 0 | 5ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | fallback | 0 | 5ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | fallback | 0 | 5ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 6ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 8ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | fallback | 0 | 3ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 3ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 6ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | fallback | 0 | 5ms | PASS |
