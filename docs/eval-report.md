# DataAgent Evaluation Report

- LLM: `real` | 平台: `real` | 模型: `deepseek-v4-flash`
- eval_date: `2023-10-14` | cassette: `-`
- 时间: 2026-08-13 10:49:32

> ⚠️ 说明：本快照为 2026-08-13 10:49 真实 LLM 评测（deepseek-v4-flash）。
> 6 个 ERROR（c07/c09/c12/c15/c16/c20）由 BUG-003（LLM 输出 `chartType`，Java DTO 未忽略未知字段 → 500）引起，当日已修复（DTO 加 `@JsonIgnoreProperties`）。
> 修复后重跑被 DeepSeek 账户余额不足（HTTP 402 Insufficient Balance）阻塞，待充值后重跑更新本报告。

## Metrics

| Metric | Score | Detail |
|---|---:|---:|
| 评测可用性 | 71% | 15/21 |
| 端到端成功率 | 33.33% | 5/15 |
| 口径核心正确率 (L1) | 80.00% | 8/10 |
| 严格全字段正确率 (L2) | 50.00% | 5/10 |
| 平均字段匹配率 (L3) | 75.00% | judged=10 |
| 自动修复成功率 | 33.33% | 12 cases retried |
| 高风险拦截率 | 0.00% | 2 cases |
| 延迟 p50 / p95 | 43364ms / 97751ms | - |

## 分项正确率 (L4)

| Field | Accuracy |
|---|---:|
| intent | 80.00% |
| metrics | 80.00% |
| dimensions | 60.00% |
| time_range | 80.00% |
| filters | 80.00% |
| ordering | 70.00% |

## Cases

| Case | Type | Result | Status | Source | Retry | Latency | Reason |
|---|---|---|---|---|---:|---:|---|
| c01_category_trend | text2sql | FAIL | SUCCESS | - | 3 | 51980ms | final report missing required fields |
| c02_category_total | text2sql | FAIL | SUCCESS | - | 3 | 27960ms | final report missing required fields |
| c03_last7d_daily_plays | text2sql | FAIL | SUCCESS | - | 3 | 38179ms | final report missing required fields |
| c04_completion_rate | metric | FAIL | SUCCESS | - | 0 | 10299ms | final report missing required fields |
| c05_food_plays | text2sql | PASS | SUCCESS | - | 2 | 54636ms | PASS |
| c06_top10_videos | text2sql | PASS | SUCCESS | - | 3 | 43364ms | PASS |
| c07_compare_food_game_trend | text2sql | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%AF%B9%E6%AF%94%E7%BE%8E%E9%A3%9F%E5%92%8C%E6%B8%B8%E6%88%8F%E5%88%86%E7%B1%BB%E7%9A%84%E6%92%AD%E6%94%BE%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c08_oct1to7_plays | text2sql | PASS | SUCCESS | - | 1 | 22355ms | PASS |
| c09_likes_trend | text2sql | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%90%84%E5%88%86%E7%B1%BB%E7%82%B9%E8%B5%9E%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c10_engagement_rate | metric | PASS | SUCCESS | - | 2 | 40259ms | PASS |
| c11_shares_total | text2sql | FAIL | SUCCESS | - | 3 | 21769ms | final report missing required fields |
| c12_food_trend | text2sql | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E7%BE%8E%E9%A3%9F%E7%B1%BB%E8%A7%86%E9%A2%91%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c13_lastweek_plays | text2sql | FAIL | SUCCESS | - | 0 | 48354ms | final report missing required fields |
| c14_answer_structure | answer_quality | FAIL | SUCCESS | - | 3 | 84274ms | final report missing required fields |
| c15_hard_guard_retry | hard_guard | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E5%90%84%E5%88%86%E7%B1%BB%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c16_dq_retry | dq | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E5%90%84%E5%88%86%E7%B1%BB%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c17_dq_warning | dq | FAIL | SUCCESS | - | 3 | 60661ms | final report missing expected keywords |
| c18_detail_playback | risk | FAIL | SUCCESS | - | 3 | 129198ms | status=SUCCESS expected=WAITING_APPROVAL |
| c19_detail_without_time | risk | FAIL | SUCCESS | - | 1 | 55891ms | status=SUCCESS expected=WAITING_APPROVAL |
| c20_open_analysis | open | ERROR | ERROR | - | 0 | 0ms | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E6%92%AD%E6%94%BE%E6%83%85%E5%86%B5&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c21_open_reason | open | PASS | SUCCESS | - | 0 | 26755ms | PASS |

## ERROR 用例（环境性失败，不计入 judged）

| Case | Reason |
|---|---|
| c07_compare_food_game_trend | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%AF%B9%E6%AF%94%E7%BE%8E%E9%A3%9F%E5%92%8C%E6%B8%B8%E6%88%8F%E5%88%86%E7%B1%BB%E7%9A%84%E6%92%AD%E6%94%BE%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c09_likes_trend | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%90%84%E5%88%86%E7%B1%BB%E7%82%B9%E8%B5%9E%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c12_food_trend | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E7%BE%8E%E9%A3%9F%E7%B1%BB%E8%A7%86%E9%A2%91%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c15_hard_guard_retry | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E5%90%84%E5%88%86%E7%B1%BB%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c16_dq_retry | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E5%90%84%E5%88%86%E7%B1%BB%E6%92%AD%E6%94%BE%E9%87%8F%E8%B6%8B%E5%8A%BF&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
| c20_open_analysis | ERROR: HTTPStatusError: Server error '500 ' for url 'http://localhost:8080/api/agent/analyze?userId=eval&message=%E5%88%86%E6%9E%90%E6%92%AD%E6%94%BE%E6%83%85%E5%86%B5&nocache=true&includeDebug=true'
For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500 |
