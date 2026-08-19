## 1. ResultComparator

- [ ] 1.1 `result_comparator.py`：exact 断言（数值+容差）、trend_pattern 断言（关键点方向/模式）、top_set 断言（集合+可选顺序）
- [ ] 1.2 单测：三类断言通过/失败边界（容差、方向、集合漏项/错序）、非可断言类型返回 None

## 2. cases 标注

- [ ] 2.1 挑 10-15 个结果可确定用例（aggregate/trend/ranking 各覆盖）
- [ ] 2.2 跑一次 real 评测取真值 → cases.yaml 标 `expected_result`（按 D1 格式）

## 3. runner R1

- [ ] 3.1 runner 聚合 R1（可断言口径）、mock 平台 R1=N/A、L1 错 → R1=N/A
- [ ] 3.2 报告：R1 与 L1-L4 并列 + `L1 对 + R1 错` 交叉诊断清单
- [ ] 3.3 单测：R1 聚合（mock 数据造 exact/trend/top_set 结果）

## 4. 评测与回归

- [ ] 4.1 Python pytest + ruff 全绿
- [ ] 4.2 real 评测（--llm real --platform real）：R1 数值 + 交叉诊断
- [ ] 4.3 --memory off N=45 回归（mock 平台 L1-L4 零回退）
- [ ] 4.4 metrics-report 新增 R1 维度；开发日志追加

## 5. 收尾

- [ ] 5.1 全量终验（pytest + ruff）；提交并推送分支
