## 0. 数据扩展准备（先构造后定稿）

- [x] 0.1 构造 25 个新 golden 候选（分类矩阵：multi_metric / multi_filter / ranked_time / cross_table / longtail_ambiguous），真实 LLM 探测定稿 → 收敛到 +20 入 cases.yaml
- [x] 0.2 构造 15-25 条难层候选（冷门指标叫法/间接说法/歧义/长尾/业务黑话），与既有易层去重，标 `difficulty: hard`（筛选/band 判定在 2.2）

## 1. 数据入库与校验

- [x] 1.1 cases.yaml +20（golden_spec + category + difficulty）；单测：新增用例 golden 指标都在 metric_catalog、golden_spec 完整可判定
- [x] 1.2 synonym_cases.yaml +15 难层（difficulty 字段；既有 20 条标 easy）；单测：加载校验 + 与易层无重复改写

## 2. runner 适配与难层筛选

- [x] 2.1 runner 透传 difficulty + 实验报告按难度分层（easy/hard：N、组 A L1、组 B L1、注入增益）
- [x] 2.2 难层筛选脚本 `app/eval/hard_layer_filter.py`：组 A（--memory off）跑难层候选 **+ 运行时 band 计算（复用 _compute_synonym_bands）** → 输出三列判定表（**组 A L1 / band / 判定**）；**真难层 = 组A错 且 band=inject**；band=miss 归 miss 泛化层；单测：脚本可复现（mock 管道）+ band 判定正确

## 3. 实验

- [x] 3.1 N=45 全量 --memory off 基线（真实 LLM）：**既有 25 例子集** L1-L4 与 N=25 基线一致（子集对比），N=45 整体单独报告
- [x] 3.2 --memory on 难层注入实验：**只统计 band=inject 真难层子集** → 组 B 对比 → easy/hard + miss 泛化层分层报告（含逐例翻转四列表，最小声明"至少 1 例翻转"）

## 4. 收尾

- [x] 4.1 Python pytest 全绿 + ruff clean
- [x] 4.2 docs/metrics-report.md 更新：N=45 基线 + 难度分层注入收益
- [x] 4.3 更新 docs/开发日志.md（倒序新条目）
