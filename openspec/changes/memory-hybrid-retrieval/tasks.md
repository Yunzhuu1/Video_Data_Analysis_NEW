## 0. 环境与硬门槛（先验证后实现）

- [x] 0.1 环境/凭据：用户开通火山方舟 doubao-embedding 文本模型 + 创建 `ARK_API_KEY`（写进 .env，settings 加 `ark_api_key`/`ark_embedding_model`/`ark_base_url`）；`EmbeddingProvider`（httpx 封装，可注入/mock）单测：mock 返回固定向量、失败 → 告警 + 返回 None（降级 difflib）
- [x] 0.2 硬门槛（判定式可执行，2026-08-18 已实测修订）：标定脚本跑同义集 20 条 vs 沉淀记忆 + 近重复对的分布，验证「近重复 ≥ hit_t（≈0.95）且 ≥60% 同义条目 ≥ inject_t（≈0.80）」；**门槛必须真实 API 跑**（mock 仅用于管道单测，不用于门槛判定）；**毒化保护由 metrics_consistent（c25 反例）承担，不做相似度分离**（一字差指标对任何相似度都分不开，实测已证）；不满足 → 回 design

## 1. 存储与检索核心

- [x] 1.1 LanceDB VectorStore：`memory.lance/` 单表（norm_question/resolved_intent/metric_codes/hit_count/last_hit_at/resolver_hash/embedding_model/embedding）+ HNSW 向量索引 + norm_question FTS 索引 + namespace 过滤；存量 SQLite 数据导入 + 惰性回填（**每 search ≤10 条**，启动后台预回填）；`VectorStore` 接口抽象（store 可替换，未来迁 Qdrant）；单测（schema/索引/导入/回填有界/WAL/模型变更失效重算）
- [x] 1.2 LanceDB FTS（BM25）可用性验证：中文短句命中排序单测；若切分质量不足 → 回退自研 BM25 或接方舟 sparse（写进报告）
- [x] 1.3 HybridRetriever（精确快路径 + **LanceDB 向量 search + FTS search 分开查 + D4 自算融合** + 双阈值 + 降级 difflib），实现/修正 Retriever 协议（补 namespace 参数）；**inject 示例按 intent 去重（top-3 尽量跨 intent）**；单测三档边界 + 毒化对不命中 + 降级路径（embedding=None → 行为同现状）+ inject intent 去重

## 2. 接入与配置

- [x] 2.1 nodes.py 用 build_retriever()/VectorStore 工厂替换直接实例化（settings 决定 hybrid/text）；融合权重 w 与阈值走 settings
- [x] 2.2 阈值标定脚本 `app/eval/calibrate_thresholds.py`：**路径 B 定死**——LanceDB 向量 search 与 FTS search 分开查，按 D4 公式自算融合（cos_norm=max(0,cos)；bm25_norm=score/top1；score=w·cos_norm+(1−w)·bm25_norm）调 EmbeddingProvider 输出同义集/毒化对/近重复对三组分布 → 定 hit/inject 阈值与 w → 写入 settings + 报告三变量（`hybrid(doubao-embedding-<model>)/hit_t-inject_t/w`）；单测：标定脚本可复现（同输入同输出，mock 仅管道）

## 3. 实验与报告闭环

- [x] 3.1 **修复 review P1（eval-metrics 遗留）**：`_compute_synonym_bands` 改为调用真实检索器 `search()` 取 top-1 band（与 nodes.py 同一工厂/同一判定，含 metrics_consistent + catalog + acceptable 复检），禁止内联重写打分；删除 platform 死代码（real 分支不可达）；补一致性单测：seed 一条 metric 不一致的相似条目 → 断言 runner band ≠ 运行时 hit（兑现"零偏差"承诺，向量化后不红）
- [x] 3.2 **review 次要项**：`_seed_memory` 失败补日志（不再静默吞错）；metrics-report 口径修正——real+real 时 `tokens_total` 显示 0（非 None）；重复对 token 归因口径（r1+r2 进单桶）在报告注明
- [ ] 3.3 exp2/exp3 重跑（真实 LLM）：**跑前探测 embedding 可用性，不可用则实验标 DEGRADED（报告显式注明，防 N_inject=0 归因污染）**；记录 N_hit/N_inject/N_miss（预期 inject 带首次可填充）、注入子集 L1 对比、**近重复 hit 召回（较 difflib 基线提升 ≥50%）**、毒化对精度、**注入示例 intent 分布（可审计）**
- [ ] 3.4 --memory off 全量回归 L1-L4 不回退 + 同问同答 100% 不回退 + 毒化反例不命中

## 4. 收尾

- [ ] 4.1 Python pytest 全绿 + ruff clean
- [ ] 4.2 docs/metrics-report.md 更新：记忆价值节（检索器三变量 + 新 band 分布 + 注入/冷热新结果）+ token 口径修正（real+real 显示 0）+ 重复对归因注明
- [ ] 4.3 更新 docs/开发日志.md（倒序新条目）
