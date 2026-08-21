# Lineage-aware Planning：可复现评测摘要

日期：2026-08-21  
范围：单指标 aggregate/trend/ranking；total_plays/total_likes/completion_rate/video_revenue；最多两跳、仅有向 N:1/1:1。

## 确定性硬门槛

| 门槛 | 结果 |
|---|---:|
| 固定 ResolvedIntent Path Recall | 8/8 |
| 预期拒绝（detail / 多指标） | 2/2 |
| judged 计划选择 | 2/2 |
| 非法 plan ID 拒绝 | 1/1 |
| 首次非法后合法重选协议 | 1/1 |
| Java/Python canonical fixture hash | 一致 |
| Java/Python repository snapshot hash | 一致（catalogVersion=`2ed1b7d6...a235`） |
| 代表性 SQL 真实 MySQL EXPLAIN | 4/4 |

命令：

```bash
cd agent-engine
PYTHONPATH=. .venv/bin/python -m app.eval.runner --lineage-eval --llm mock --platform mock --memory off
```

## 真实 LLM 方向性观测

固定候选、只调用 QueryPlannerAgent 两次：

| 问题 | 选择 | reason | prompt chars | latency |
|---|---|---|---:|---:|
| 各分类点赞量 | `total_likes_daily` | LOW_COST | 1078 | 3316ms |
| 实时各分类点赞量 | `total_likes_fact` | REALTIME_REQUIRED | 1080 | 2492ms |

N=2 仅证明 skill 在本轮按预期工作，不宣称统计显著性或通用规划准确率。

## N=61 端到端回归

embedding/memory 均关闭，平台 mock，R1 由 runner 通过 MySQL CLI 独立执行：

| 模式 | 可用 | E2E | L1 | R1 |
|---|---:|---:|---:|---:|
| planning=off | 61/61 | 61/61 | 49/49 | 29/29 |
| planning=active | 61/61 | 59/61 | 48/49 | 29/29 |

active 的单轮 L1 差异来自 `n25_longtail` 的真实 Semantic LLM 输出变为 `daily_active_users`，发生在 Planner 之前；两个 E2E 失败是最终报告字段缺失。二者均非计划 SQL/R1 回退，但仍如实保留，不能把单轮结果包装成“准确率提升”。真正可复现的无回退证据是 planning=off、固定 intent path gates、SQL EXPLAIN 与 active R1=29/29。

## 已知边界

- 多指标、detail、三跳和未知 binding 明确走 legacy，不做近似计划。
- cardinality 是 catalog-declared 业务承诺，不是自动从数据库发现的完整血缘。
- Planner 不是自由写 SQL；LLM 只在系统枚举的合法 plan ID 中做成本/新鲜度选择。
- 本轮不包含图数据库、完整 grain algebra、在线 Skill 自动发布或生产级成本优化器。
