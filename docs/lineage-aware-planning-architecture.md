# 血缘感知 Query Planner MVP

## 一句话

Semantic Agent 决定“查什么”，确定性 Enumerator 根据冻结的血缘/指标/schema 快照生成合法物理计划，QueryPlannerAgent 只在多个合法方案存在成本与新鲜度取舍时选择 plan ID，Validator 复验后由确定性 Compiler 生成 SQL。

## 主链路

```text
SEMANTIC_RESOLVE (ResolvedIntent)
  → PLAN_ENUMERATE (完整 fieldRoutes，禁止 LLM 拼 JOIN)
  → AUTO_SINGLE / AUTO_POLICY / QueryPlannerAgent
  → PLAN_VALIDATE (版本、字段用途、边方向、候选成员)
  → SQL_SYNTHESIZE (selected plan 或 legacy)
  → SQL_HARD_GUARD → EXECUTE → DQ → ANSWER
```

## 三个关键不变式

1. **LLM 不创造数据库事实**：Planner 只能复制本轮 candidate `planId`，输出 SQL/table/column/join 会被拒绝。
2. **选择路径就是执行路径**：计划冻结 GROUP_BY/FILTER/ORDERING/TIME_FILTER/TIME_BUCKET 的全部 `fieldRoutes`；Validator 和 Compiler 禁止重新 BFS。
3. **同版本同计划同 SQL**：run snapshot 同时冻结 lineage overlay、metric definitions、schema projection；三者组合 hash 进入 planId，Compiler 不回读可变 catalog。

## 为什么不用图数据库

当前垂直切片只有 6 张相关表、6 条 metric path 和 4 条安全边。JSON 能提供 Git review、版本回放、跨语言 fixture 与 mock/real 同源；图数据库在动态血缘查询、复杂影响分析和大规模元数据治理出现之前只会增加部署与一致性成本。

## 回滚

`LINEAGE_PLANNING_MODE=off|shadow|active`：off 完全走旧合成器；shadow 只枚举/记录；active 才使用验证通过的计划。非 MVP 或验证耗尽始终回到 legacy，legacy 失败才 raw LLM SQL。
