## 1. Token 计量

- [x] 1.1 TokenMeter（累加 + snapshot/reset）单测
- [x] 1.2 LLMClient._call 记录 usage 到 meter（单测：usage 解析/累加）
- [x] 1.3 runner 每 case 快照归因 tokens + 报告展示（单测：差值归因）

## 2. 同义集与实验入口

- [x] 2.1 synonym_cases.yaml（20 条，5 类变换 × 4，含 golden_spec + source_case；**不静态标 band**）
- [x] 2.2 runner 支持同义集实验入口（--synonym-cases；组 A 无记忆 / 组 B 有记忆 + 沉淀）；**band 分层 = 沉淀后对每条同义问题真实 retriever.search 取 top-1**
- [x] 2.3 单测：同义集加载校验（含 golden 覆盖）；band 分层与检索器输出一致性断言（**不绑定具体 band 值**，避免向量化后红）+ 阈值标定方法单测

## 3. 三个实验

- [x] 3.1 直通收益实验（hit 波段）：重复对第一遍 vs 第二遍延迟/用例总 token 差（≈ 解析阶段消除）
- [x] 3.2 注入收益实验（仅 inject 波段子集）：无记忆 vs 有记忆 L1 成功率 + inject 命中率；miss 子集单独报告；实验前检查：沉淀后算全量运行时 band，inject 子集 < 8 条（阈值可配）→ 警告 + 报告显式标注「样本不足，结论仅方向性」（不阻断但可见）
- [x] 3.3 冷热启动实验（检索侧）：空记忆 vs seed 预置记忆成功率/延迟（区别于全链路注入实验）

## 4. 指标报告

- [x] 4.1 整理历史轨迹表（端到端/L1/拦截率/命中率逐轮，附 commit）
- [x] 4.2 撰写 docs/metrics-report.md（正确性/安全/效率/记忆价值按波段分层 + 实验协议 + **局限说明** + 逐条审计四列表 + **检索器/阈值/embedding 模型三变量配置** + **各波段样本量 N_hit/N_inject/N_miss 并列输出**）
- [x] 4.3 真实评测跑实验：直通/注入/冷热（--memory on/off 各基线）
- [x] 4.4 Python pytest + ruff 全绿；更新 docs/开发日志.md
