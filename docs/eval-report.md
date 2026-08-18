# DataAgent Evaluation Report

- LLM: `real` | 平台: `mock` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-18 13:27:00

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 100% | 25/25 |
| 端到端成功率 | 92.00% | 23/25 |
| 口径核心正确率 (L1) | 100.00% | 13/13 |
| 严格全字段正确率 (L2) | 92.31% | 12/13 |
| 平均字段匹配率 (L3) | 98.72% | judged=13 |
| 自动修复成功率 | 100.00% | 2 cases retried |
| 高风险拦截率 | 100.00% | 3 cases |
| 自动放行（auto_released） | 0.00% | 0/25（非 risk 用例被拦截后自动放行） |
| 记忆命中率（memory_hit） | 0.00% | 0/25 |
| 记忆注入率（memory_inject） | 0.00% | 0/25 |
| Token 总消耗 | 73303 | 命中均值 0 / 未命中均值 2932 |
| 直通收益（重复对） | token 差均值 0 / 延迟差均值 0ms | 0/0 对命中直通（≈ 解析阶段消除） |
| 意外拦截数 | 0 | 自动放行后仍失败的用例（门禁过度拦截信号） |
| 延迟 p50 / p95 | 12252ms / 28120ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 100.00% |
| metrics | 100.00% |
| dimensions | 100.00% |
| time_range | 100.00% |
| filters | 100.00% |
| ordering | 92.31% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | PASS | SUCCESS | semantic | 0 | 27834ms | PASS |
| c02_category_total | text2sql | PASS | SUCCESS | semantic | 0 | 18373ms | PASS |
| c03_last7d_daily_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10670ms | PASS |
| c04_completion_rate | metric | PASS | SUCCESS | semantic | 0 | 12734ms | PASS |
| c05_food_plays | text2sql | PASS | SUCCESS | semantic | 0 | 10439ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | semantic | 0 | 23491ms | PASS |
| c07_compare_food_game_trend | text2sql | FAIL | SUCCESS | semantic | 0 | 10360ms | final report missing required fields |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | semantic | 0 | 25696ms | PASS |
| c09_likes_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9816ms | PASS |
| c10_engagement_rate | metric | PASS | SUCCESS | semantic | 0 | 12211ms | PASS |
| c11_shares_total | text2sql | PASS | SUCCESS | semantic | 0 | 9536ms | PASS |
| c12_food_trend | text2sql | PASS | SUCCESS | semantic | 0 | 9404ms | PASS |
| c13_lastweek_plays | text2sql | PASS | SUCCESS | semantic | 0 | 12252ms | PASS |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | semantic | 0 | 8327ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | PASS | SUCCESS | fallback | 1 | 15783ms | PASS |
| c16_dq_retry | dq | PASS | SUCCESS | fallback | 1 | 28329ms | PASS |
| c17_dq_warning | dq | PASS | SUCCESS | semantic | 0 | 19417ms | PASS |
| c18_detail_playback | risk | PASS | WAITING_APPROVAL | semantic | 0 | 6883ms | PASS |
| c19_detail_without_time | risk | PASS | WAITING_APPROVAL | fallback | 0 | 24683ms | PASS |
| c20_open_analysis | open | PASS | SUCCESS | fallback | 0 | 25206ms | PASS |
| c21_open_reason | open | PASS | SUCCESS | semantic | 0 | 28192ms | PASS |
| c22_fact_full_scan_approval | risk | PASS | WAITING_APPROVAL | fallback | 0 | 15317ms | PASS |
| c23_aggregate_full_scan_pass | text2sql | PASS | SUCCESS | semantic | 0 | 8597ms | PASS |
| c24_memory_repeat | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
| c25_memory_counterexample | memory | PASS | SUCCESS | - | 0 | 0ms | SKIPPED (memory off) |
