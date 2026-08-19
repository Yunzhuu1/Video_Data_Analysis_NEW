## 1. time_expand 纯函数

- [x] 1.1 `time_expand.py`：relative {amount, unit} + anchor_date → absolute（含端点：最近N天 = 末日往前 N-1 天）；unit day/week（month 近似 30 天标注）
- [x] 1.2 单测：7天/30天/一周/昨天到今天、含端点边界、unit 换算

## 2. 合成前展开集成

- [x] 2.1 nodes 增加 `_expand_relative_time`：relative 时查锚点（platform execute_sql `SELECT MAX(timeField)`，**timeField 取经 `_resolve_path` 解析后 source 的列**，与合成过滤同源；mock 固定 2023-10-31）→ 替换为 absolute；查询失败降级 + warning
- [x] 2.2 单测：c03 展开后合成 SQL 含 `WHERE date BETWEEN '2023-10-25' AND '2023-10-31'`；mock/real 锚点一致性

## 3. R1 扩展

- [x] 3.1 relative **可断言子集**（aggregate/trend：c03/c13/n04/n09/n10/n11 等）取真值（独立手工 SQL，锚点=数据末日）→ 标 expected_result；detail/歧义（n22/n23/n25）只验 SQL 形态
- [x] 3.2 单测：R1 对 relative 用例断言通过（修复后）

## 4. 评测与回归

- [x] 4.1 Python pytest + ruff 全绿
- [x] 4.2 --memory off N=45 回归零回退（L1-L4 不变）
- [x] 4.3 R1 评测：relative 用例全绿（修复闭环证据）
- [x] 4.4 metrics-report 更新（relative 修复 + R1 扩展）；开发日志追加

## 5. 收尾

- [x] 5.1 全量终验（pytest + ruff）；提交并推送分支
