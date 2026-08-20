## 1. 合成器：指标值过滤（HAVING）

- [ ] 1.1 filters op 扩展（>、>=、<、<=）判定：field 是指标 code → HAVING；维度 → WHERE
- [ ] 1.2 合成器生成 HAVING（**复用 SELECT 同一 agg_expr 变量** + op + value；无 GROUP BY 也支持）；MVP 限 aggregate/trend，**跨源多指标 + 指标过滤组合降级**
- [ ] 1.3 单测：指标过滤 HAVING、维度过滤 WHERE、混合（WHERE+HAVING）、非聚合误用降级

## 2. 合成器：冲突多指标（子查询 JOIN，统一解跨源 + 同源 fact 冲突）

- [ ] 2.1 任一指标组合存在来源冲突（跨 sourceTable）或 eventFilter 冲突（同源 fact 不同 filter）→ 各指标子查询（SELECT 维度键 + agg AS code FROM source GROUP BY 维度键）+ 按维度键 JOIN；维度键 expr 跨子查询一致
- [ ] 2.2 约束：共享 dims/time/filters + 粒度对齐；不对齐 → SynthesisError
- [ ] 2.3 单测：n02 子查询 JOIN SQL 形态、同源 fact 冲突（total_plays+total_likes dims=[content]）也走 JOIN、异粒度降级、同源同 filter 单 FROM 不变

## 3. prompt / 契约 / 比较器同步

- [ ] 3.1 state.py filters op Literal 扩展；semantic.py prompt 教解析数值过滤（指标 vs 维度）
- [ ] 3.2 比较器 filters 三元组比较支持新 op
- [ ] 3.3 单测：LLM prompt 示例、比较器新 op

## 4. 评测与基线

- [ ] 4.1 cases.yaml 新增 ~4 数值过滤用例 + n02 预期改 semantic；R1 真值独立重取
- [ ] 4.2 全量 pytest + ruff；--memory off N=57 回归（既有零回退）
- [ ] 4.3 R1 评测（数值过滤 + n02 解锁）；metrics-report + 开发日志

## 5. 收尾

- [ ] 5.1 全量终验（pytest + ruff）；提交并推送分支
