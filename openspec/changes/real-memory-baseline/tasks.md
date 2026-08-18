## 1. real-session 协议（runner）

- [x] 1.1 runner 增加 `--protocol real-session`（默认 `eval`）：namespace=`real-<eval_date>-<start_ts>`，一次评测一个；`--llm mock` 时报错提示（真实 LLM 才可沉淀）
- [x] 1.2 会话分组执行：从 golden 子集选 8 个代表性问题，每会话 = 首问（沉淀）→ 二问（同文本）→ 近似问（变体），近似变体复用同义集 easy 层或人工构造；近似问仅观测（band 任意分层），若演示注入需先离线校验融合分 ≥ inject_t
- [x] 1.3 单测：协议参数校验、namespace 生成、会话分组逻辑（mock 检索器下断言首问 memory_hit=false / 二问 true）

## 2. 口径分离指标

- [x] 2.1 聚合 `real_hit_rate`（二问起命中/可命中机会）、`real_consistency`（复用重复对逐字段口径）、`real_persist_hits`；所有 `real_` 指标带 x/y 原始计数 + 「N=8 方向性基线」标注；报告与场内 `memory_hit_rate` 并列并各自标注口径
- [x] 2.2 单测：构造首问未命中+二问命中的 mock 数据，断言指标数值

## 3. 跨进程持久化验证

- [x] 3.1 弱验证：第一遍会话结束后 close() store，同路径重开后再查同文本，验证命中仍在；记录 `real_persist_hits`（文件持久化口径）
- [x] 3.2 单测：临时 store 写入 → close → 重开 → 命中（SQLite 与 Lance 后端各一条）

## 4. 防污染校验

- [x] 4.1 real-session 默认只读写 `real-<ts>` namespace；`--namespace default` 显式开关仅联调用，CI/评测脚本不携带
- [x] 4.2 单测：默认模式下 default 条目数不变；显式开关可写 default

## 5. 评测与回归

- [x] 5.1 Python pytest + ruff 全绿
- [ ] 5.2 `--memory off` 全量回归（N=45 基线不回退）
- [ ] 5.3 real-session 真实评测（--llm real --platform real，或 real+mock 组合）：真实命中率/一致率 + 报告；强验证（real 模式两遍 /analyze + 重启服务器，同一 MEMORY_LANCE_PATH）记录 `real_persist_hits_strong`
- [ ] 5.4 metrics-report 新增「真实路径基线」章节；开发日志追加本次评测

## 6. 收尾

- [ ] 6.1 全量 pytest + ruff 终验；提交并推送分支
