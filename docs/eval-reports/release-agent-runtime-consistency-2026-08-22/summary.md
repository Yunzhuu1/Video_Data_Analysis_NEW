# Agent Runtime Consistency 评测汇总（2026-08-22）

> 结论：四个真实运行时 P1 已闭环；目录漂移导致的 12 个结构性不可达用例全部恢复，服务端 Lance、Run Detail 与相对时间真实链路可用。系统对抗 Readiness 仍因既有 P2 为 FAIL，不夸大为生产就绪。

## 1. 确定性门禁

- Java：65/65；Python：275/275 且自然退出；Ruff、OpenSpec strict、`git diff --check` 全绿。
- MySQL 旧库真实迁移：ACTIVE 指标 7→15；第二次启动仍为 15，全部 `version=1`。
- 业务数据未污染：`user_behavior_fact` 12764 行/checksum `27485704136149`，`metric_daily` 93 行/checksum `198120979855`，迁移前后相同。
- Catalog readiness：managed/runtime hash 均为 `91f6f54d0f2aa622b866ee302133ae8212b8064710e88a650670ccd6eb9f08b8`，missing/drifted/extra 均为空；lineage snapshot 可构建。

## 2. 12 个结构性不可达用例逐例对账

| Case | 修复前真实目录 | 修复后真实链路 | 结果 |
|---|---|---|---|
| n26_comment_rate | comment_rate 缺失→total_comments | comment_rate / semantic | reachable |
| n27_like_rate | like_rate 缺失→total_likes+total_plays | like_rate / semantic | reachable |
| n28_share_rate | share_rate 缺失→total_shares | share_rate / semantic | reachable |
| n29_avg_completion | avg_completion_ratio 缺失→completion_rate | avg_completion_ratio / semantic | reachable |
| n30_creator_revenue | creator_revenue 缺失→empty | creator_revenue / semantic | reachable |
| n31_video_revenue | video_revenue 缺失→total_plays | video_revenue / semantic | reachable |
| n32_active_creator | active_creator_count 缺失→empty | active_creator_count / semantic | reachable |
| n33_dau | daily_active_users 缺失→empty | daily_active_users / semantic | reachable |
| n34_creator_revenue_trend | creator_revenue 缺失→unresolved | creator_revenue / semantic | reachable |
| n35_comment_rate_trend | comment_rate 缺失→unresolved | comment_rate / semantic | reachable |
| n36_dau_trend | daily_active_users 缺失→empty | daily_active_users / semantic | reachable |
| n37_video_revenue_rank_trend | video_revenue 缺失→total_plays | video_revenue / semantic | reachable；R1 排序差异另列 backlog |

`n19_longtail` 的 golden 指标原本就在旧 7 指标目录，不纳入 catalog-caused 分母；本轮恰好 L1 正确，但只视为单轮观测。

## 3. N=61 真实端到端（有效 memory-off 重跑）

| 指标 | 修复前 | 修复后 |
|---|---:|---:|
| Evaluated | 61/61 | 61/61 |
| E2E | 60/61 | 60/61 |
| L1 | 36/49 | 47/49 |
| L2 | 25/49 | 31/49 |
| invalid_catalog fallback | 59/61 | 0/61 |
| R1 | 21/21 | 既有 21/21；扩展口径 28/29 |
| memory hit/inject | 0/61 / 0/61 | 0/61 / 0/61 |

剩余 L1 失败为 `n15_cross_table` 与 `n25_longtail`，属于单轮模型/低信号问题，不归因于 catalog。扩展 R1 唯一失败为 `n37_video_revenue_rank_trend` 的第 3/4 名排序差异，说明目录恢复后 R1 成功暴露了新的结果级问题。

首轮重跑误用了 memory=READY 的外部 Agent，出现 10/61 memory hit，已明确保存为 `*-invalid-memory-contaminated.*`，不进入产品指标。随后以 `MEMORY_ENABLED=false` 重启并由 `/health` 确认 DISABLED 后重跑，以上数据来自有效隔离轮次。

## 4. Runtime smoke

- `/internal/metrics` 返回 15 code；runtime status READY；lineage snapshot hash 完整。
- creator_revenue、comment_rate、daily_active_users、最近 7 天播放趋势均完成解析、合成与真实执行；需审批的 FACT 查询通过同一 SQL 恢复执行。
- 相对时间展开为 `2023-10-25..2023-10-31`，锚点与最终过滤物理路径同源，未再出现 `Invalid isoformat`。
- 新建 run 的 Run Detail HTTP 200，`finishedAt` 正常，11 个节点按执行顺序完整返回。
- Lance health READY；Agent 中间重启后同 namespace 重复问题为 `memoryHit=true / band=hit / sqlSource=memory`。

## 5. 对抗与记忆方向性结果

- Integrated adversarial：case 20/20、variant 3/3、ledger 22/22、unsafe 0/12、illegal plan rejection 6/7、recovery 3/3；Expected Disposition 12/20、R1 1/4，System Readiness 仍为 FAIL。
- Real-session N=8：二问命中 8/8、逐字段一致 8/8、close/reopen 文件持久化 8/8；第二问累计少 11,524 tokens。N=8 仅是方向性基线；服务重启强验证另已在 runtime smoke 完成单例验证。

## 6. 剩余 backlog

1. `n37` 视频收益排名趋势的稳定排序/真值契约（R1 value mismatch）。
2. `n15`、`n25` 低信号/长尾语义解析方差。
3. 对抗集 C02-C04、P02、S01/S03-S05 的处置契约差异；在独立 change 修复，不移动 expected。
4. Runner 的运行时 embedding 失败健康计数（BUG-021）仍未纳入本 change。
