## 1. 根因基线

- [x] 1.1 跑 --llm real --platform mock 语义层评测，**产出 5 个失分用例的 actual resolvedIntent vs golden 对照表**（硬门槛：D2/D3 具体规则据此确认；若实测模式与假设不符，先修订 design 再继续）
  - 实测结论：主失败模式 = **date 误入 dimensions**（c07/c12/c13）；c01/c03 偶发；c07 filters IN 已正确，对比类规则为 reinforcement

## 2. Prompt 优化

- [x] 2.1 SEMANTIC_SYSTEM_PROMPT：date 禁止入 dimensions（属 time_range.granularity）
- [x] 2.2 SEMANTIC_SYSTEM_PROMPT：各分类/按分类 → dimensions；类目限定 → filters
- [x] 2.3 补正反示例（各分类趋势 / 最近7天每天播放量 / 美食类视频播放量趋势 / 对比类）
- [x] 2.4 新增对比类规则：'对比/比较 A 和 B 分类' → dims=[category] + filters=[category IN (A,B)]（与单分类限定边界明确）

## 3. 确定性兜底

- [x] 3.1 resolve() 内后处理（question 可用处，非 _normalize）：dimensions 含 date → 移除（**不强制补 day**；如需按"天/每天/每日"关键词触发）
- [x] 3.2 resolve() 内：含"各分类"且 dimensions 空且无 category filter → 补 category（question 文本匹配）
- [x] 3.3 单测：date 清洗、各分类补全、不误伤其它用例

## 4. 回归与验收

- [x] 4.1 Python pytest + ruff 全绿
- [x] 4.2 --llm real --platform mock：**L4 dimensions ≥85% 且 L2 ≥70%**（L2 同为 resolvedIntent 对比，不依赖执行）；**c07 对比类 dims+filters 同时正确**
  - 实测：L2 100%、L3 100%、dimensions 失分 0
- [x] 4.3 --llm real --platform real：L4 dimensions ≥85%、L2 ≥70%，且 L1/L3 不回退
  - 实测：L2 100%、L3 100%、L4 dimensions 100%、L1 100%、端到端 95.65% 不回退
- [x] 4.4 更新 docs/eval-report.md 与 docs/开发日志.md
