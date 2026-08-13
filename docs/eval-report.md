# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-chat`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-13 10:11:18

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 21/21 |
| 端到端成功率 | 76.19% | 16/21 |
| 口径核心正确率 (L1) | 0.00% | 0/13 |
| 严格全字段正确率 (L2) | 0.00% | 0/13 |
| 平均字段匹配率 (L3) | 0.00% | judged=13 |
| 自动修复成功率 | 0.00% | 0 cases retried |
| 高风险拦截率 | 0.00% | 2 cases |
| 延迟 p50 / p95 | 555ms / 629ms | - |

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
| c01_category_trend | text2sql | PASS | SUCCESS | - | 0 | 590ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | - | 0 | 528ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | - | 0 | 503ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | - | 0 | 509ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | - | 0 | 514ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | - | 0 | 495ms | PASS |
| c07_compare_food_game_trend | text2sql | PASS | SUCCESS | - | 0 | 503ms | PASS |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | - | 0 | 512ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | - | 0 | 562ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | - | 0 | 542ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | - | 0 | 583ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | - | 0 | 536ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | - | 0 | 1087ms | PASS |
| c14_answer_structure | answer_quality | PASS | SUCCESS | - | 0 | 594ms | PASS |
| c15_hard_guard_retry | hard_guard | FAIL | SUCCESS | - | 0 | 558ms | sql_retry_count=0 expected=1 |
| c16_dq_retry | dq | FAIL | SUCCESS | - | 0 | 555ms | sql_retry_count=0 expected=1 |
| c17_dq_warning | dq | FAIL | SUCCESS | - | 0 | 554ms | final report missing expected keywords |
| c18_detail_playback | risk | FAIL | SUCCESS | - | 0 | 569ms | status=SUCCESS expected=WAITING_APPROVAL |
| c19_detail_without_time | risk | FAIL | SUCCESS | - | 0 | 577ms | status=SUCCESS expected=WAITING_APPROVAL |
| c20_open_analysis | open | PASS | SUCCESS | - | 0 | 581ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | - | 0 | 629ms | PASS |
