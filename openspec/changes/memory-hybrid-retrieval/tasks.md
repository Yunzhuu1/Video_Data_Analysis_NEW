## 0. 环境与硬门槛（先验证后实现）

- [ ] 0.1 安装 sentence-transformers + torch；下载 bge-small-zh-v1.5（记录模型路径/哈希，可走 HF 镜像）；EmbeddingProvider 懒加载单测（加载失败 → 告警 + 返回 None）
- [ ] 0.2 硬门槛（判定式可执行）：离线跑同义集 20 条 vs 沉淀记忆 + 毒化对（点赞量/播放量）的融合分分布，验证「存在阈值区间 (inject_t, hit_t] 使 毒化对全部 < hit_t 且 ≥60% 同义注入条目 > inject_t」；不满足 → 回 design 改方案（仿 semantic-dimensions 根因基线）

## 1. 存储与检索核心

- [ ] 1.1 MemoryStore 加 `embedding TEXT`（JSON list[float]，格式写死）+ `embedding_model TEXT` 列（ALTER 迁移 + 存量惰性回填，**每 search 至多补算 10 条**）；upsert 同步写 embedding；单测（迁移/回填有界/模型变更失效重算）
- [ ] 1.2 BM25 实现（std 自实现，1-2 字切分，可单测命中排序）
- [ ] 1.3 HybridRetriever（精确快路径 + cosine + BM25 融合 + 双阈值 + 降级 difflib），实现/修正 Retriever 协议（补 namespace 参数）；**inject 示例按 intent 去重（top-3 尽量跨 intent）**；单测三档边界 + 毒化对不命中 + 降级路径（embedding=None → 行为同现状）+ inject intent 去重

## 2. 接入与配置

- [ ] 2.1 nodes.py 用 build_retriever() 工厂替换直接实例化（settings 决定 hybrid/text）；融合权重 w 与阈值走 settings
- [ ] 2.2 阈值标定脚本 `app/eval/calibrate_thresholds.py`：按 design D4 公式（cos_norm=max(0,cos)；bm25_norm=score/top1；score=w·cos_norm+(1−w)·bm25_norm）输出同义集/毒化对/近重复对三组分布 → 定 hit/inject 阈值与 w → 写入 settings + 报告三变量；单测：标定脚本可复现（同输入同输出）

## 3. 实验与报告闭环

- [ ] 3.1 **修复 review P1（eval-metrics 遗留）**：`_compute_synonym_bands` 改为调用真实检索器 `search()` 取 top-1 band（与 nodes.py 同一工厂/同一判定，含 metrics_consistent + catalog + acceptable 复检），禁止内联重写打分；删除 platform 死代码（real 分支不可达）；补一致性单测：seed 一条 metric 不一致的相似条目 → 断言 runner band ≠ 运行时 hit（兑现"零偏差"承诺，向量化后不红）
- [ ] 3.2 **review 次要项**：`_seed_memory` 失败补日志（不再静默吞错）；metrics-report 口径修正——real+real 时 `tokens_total` 显示 0（非 None）；重复对 token 归因口径（r1+r2 进单桶）在报告注明
- [ ] 3.3 exp2/exp3 重跑（真实 LLM）：记录 N_hit/N_inject/N_miss（预期 inject 带首次可填充）、注入子集 L1 对比、**近重复 hit 召回（较 difflib 基线提升 ≥50%）**、毒化对精度、**注入示例 intent 分布（可审计）**
- [ ] 3.4 --memory off 全量回归 L1-L4 不回退 + 同问同答 100% 不回退 + 毒化反例不命中

## 4. 收尾

- [ ] 4.1 Python pytest 全绿 + ruff clean
- [ ] 4.2 docs/metrics-report.md 更新：记忆价值节（检索器三变量 + 新 band 分布 + 注入/冷热新结果）+ token 口径修正（real+real 显示 0）+ 重复对归因注明
- [ ] 4.3 更新 docs/开发日志.md（倒序新条目）
