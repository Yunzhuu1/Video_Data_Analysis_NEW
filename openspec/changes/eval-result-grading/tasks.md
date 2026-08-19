## 1. ResultComparator

- [x] 1.1 `result_comparator.py`：exact / exact_per_key（带维度多行）/ trend_pattern（单序列+多序列按序列键）/ top_set（集合+可选顺序）断言
- [x] 1.2 单测：断言通过/失败边界（容差、方向、集合漏项/错序、exact_per_key 多行）、失败原因分类、非可断言类型返回 None

## 2. cases 标注

- [x] 2.1 挑 10-15 个结果可确定用例（aggregate/trend/ranking 各覆盖）
- [x] 2.2 用**独立于合成器的手工 SQL** 直接查库取真值 → cases.yaml 标 `expected_result` + `truth_source`（手工 SQL/查询时间/seed 版本）

## 3. runner R1

- [x] 3.1 runner 聚合 R1（可断言口径）、mock 平台 R1=N/A、L1 错 → R1=N/A、失败原因分类（sql_error/exec_error/value_mismatch）
- [x] 3.2 报告：R1 与 L1-L4 并列 + `L1 对 + R1 错` 交叉诊断清单（仅 value_mismatch）
- [x] 3.3 单测：R1 聚合（mock 数据造 exact/trend/top_set 结果）

## 4. 评测与回归

- [x] 4.1 Python pytest + ruff 全绿
- [x] 4.2 real 评测（--llm real --platform real）：R1 数值 + 交叉诊断
- [x] 4.3 --memory off N=45 回归（mock 平台 L1-L4 零回退）
- [x] 4.4 metrics-report 新增 R1 维度；开发日志追加

## 5. 收尾

- [ ] 5.1 全量终验（pytest + ruff）；提交并推送分支
