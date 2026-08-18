## Context

现状（semantic-memory / memory-namespace-isolation 已落地）：`TextSimilarityRetriever` 用 `difflib` 字符相似度 + 双阈值（0.95 hit / 0.85 inject），`SEMANTIC_RESOLVE` 前置：hit → 直通复用 ResolvedIntent，inject → few-shot 注入，miss → 现状 LLM。metrics-report 实测（exp2/exp3）：同义集 20 条与沉淀记忆相似度 0.455–0.778，**全部 miss**，注入/冷热实验因 N_inject=0 无法量化。离线复核：字二元组 Jaccard/Cosine 也分不开（min/max 分布更差）——**字面相似度对"语义级改写"（播放量→观看量、各分类→各类别）天然失效，只有语义 embedding 能把改写映射到相近向量**。

`docs/记忆系统设计.md` §5.1（2026-08 调研）结论：本场景抄成熟机制不抄框架——DAIL-SQL 示例检索范式 + Mem0 multi-signal 融合（语义+BM25）+ CoALA 分型叙事。检索层设计输入已写入 §5.2：语义向量为主 + BM25 词面为辅 + 阈值重标定 + 时效衰减 + difflib 降级保险。

## Goals / Non-Goals

**Goals：**
- 让同义集的语义近义改写落进 inject 带（exp2/exp3 从"N_inject=0"变为可量化），记忆价值从"命中直通 + token 省 21%"扩展到"注入泛化可测"。
- 提升真实流量的 hit 召回（近重复/语义改写问题更稳直通）与精度（毒化对不误命中）。
- 阈值标定方法可复现、可解释（面试可讲"为什么是这个数"）。
- 保持既有确定性契约：同问同答 100% 一致、--memory off 回归 L1-L4 不回退、记忆失败不打断主链路。

**Non-Goals：**
- 向量索引基建（FAISS/HNSW/pgvector）：当前规模 SQLite 存向量 + 线性 scan 毫秒级，非目标（写死防蔓延）。
- 多用户/多租户记忆、记忆淘汰策略（仅沿用 hit_count/last_hit_at 排序）。
- AST 骨架相似度（DAIL-SQL 第二维，属模板提炼 change，后续）。
- 指标别名表（语义层范畴，后续 change）。

## Decisions

### D1：Embedding 来源——本地 bge-small-zh-v1.5 + 懒加载 + 降级兜底
- **选**：`sentence-transformers` 加载本地 `bge-small-zh-v1.5`（~100MB 模型，CPU 短句单条 ~10-50ms）。
- **替代考虑**：① API embedding（SiliconFlow/BAAI 等）→ 每次查询依赖网络（本项目网络不稳，致命）+ 有成本；② 纯 BM25/词级 → 离线已实测分不开同义改写；③ 不升级（保持现状）→ 注入实验永久空转。
- **懒加载单例 + 加载失败降级**：EmbeddingProvider 首次使用时加载；失败仅告警（`memory disabled embedding: ...`），检索降级 `TextSimilarityRetriever`（现状行为 0.95/0.85）——与"记忆失败不打断主链路"哲学一致。
- **模型版本**：`embedding_model` 列存模型名+内容哈希，模型变更 → 全量失效重算。

### D2：检索架构——三层混合 HybridRetriever（实现既有 Retriever 协议）
```
search(question, namespace)
  ├─ ① 精确匹配快路径：norm_question 完全相等 → hit（score=1.0）
  │     确定性契约（同问同答 100%）不依赖模型，模型漂移不影响
  ├─ ② 语义信号：query embedding vs 条目缓存 embedding 的 cosine
  ├─ ③ 词面信号：BM25（std 自实现，中文按 1-2 字切分）
  │     融合分 = w·cosine + (1−w)·bm25_norm（w 初值 0.7，标定后定）
  └─ 双阈值（hit ≥ hit_t / inject ≥ inject_t）→ 同现状 band 语义
```
- **替代考虑**：纯向量 → 可能漏精确词匹配（"最近7天"这类字面关键）；纯 BM25 → 漏语义改写。融合是 Mem0 multi-signal 的落地形态。
- 命中后安全网不变：`_catalog_valid` + `metrics_consistent` + `_acceptable_intent` 复检。
- **inject 示例的意图一致性（P2-2）**：语义相似 ≠ 意图相同（"各分类播放量排名"=ranking vs "各分类播放量趋势"=trend，cosine 很高）。`metrics_consistent` 只保护 hit 路径，inject 路径无一致性防护。策略：**注入示例按 intent 去重**（top-3 尽量覆盖不同 intent，同 intent 只取相似度最高一条）+ **报告记录注入示例的 intent 分布**（可审计，防负迁移）。

### D3：存储——SQLite 加 embedding 列，写时缓存，不引入向量库
- `semantic_memory` 表 ALTER 加 `embedding TEXT` + `embedding_model TEXT`；存量迁移 + 惰性回填。
- **embedding 格式写死为 JSON**（`json.dumps(list[float])`，bge-small-zh 512 维 ≈ 1-2KB/条）：规模小开销可忽略，可调试优先；二进制作未来规模增长时的优化项（P3）。
- **回填延迟有界（P2-3）**：每 search 至多补算 N=10 条（带"已回填"标记），首个非精确查询延迟有界（10×10-50ms ≈ 0.5s）；启动时可选后台任务预回填；**①精确匹配快路径在回填前即可命中**（模型的懒加载/首载是一次性 ~1-2s，可接受，写进报告）。
- upsert 时同步写 embedding（写钩子路径）；record_hit 不重算。
- **为何不加 FAISS**：规模几十~上百条，线性 cosine 毫秒级；FAISS 是规模问题的解，当前是过度工程（写入 Non-Goals）。

### D4：融合评分与阈值重标定（离线脚本，可复现）
- **评分公式（P2-1，归一化写死，保证标定可复现）**：
  - `cos_norm = max(0.0, cos)`（cosine ∈ [-1,1] 裁剪到 [0,1]）
  - `bm25_norm = bm25_score / top1_bm25_score`（候选集内除以最高分 → [0,1]；BM25 无界且语料=记忆库几十条、IDF 不稳定，用候选集内相对分）
  - `score = w·cos_norm + (1−w)·bm25_norm`（w 初值 0.7，标定后定）
- **标定方法**（沿用 design 既有方法论，落地为脚本 `app/eval/calibrate_thresholds.py`）：
  - hit 阈值 = 「毒化对（点赞量 vs 播放量）全部落在 hit 之下」的最小值
  - inject 阈值 = 「期望注入的同义条目全部落在 inject 区间」的最大值
  - 输出三组分布表（同义集 20 条 / 毒化对 / 近重复对）→ 定阈值与 w → 写 settings + 报告
- **硬门槛（先验证后实现，判定式可执行——P1）**：任务 0.2 通过条件 =
  `存在阈值区间 (inject_t, hit_t] 使 毒化对全部 < hit_t 且 ≥60% 的同义注入条目 > inject_t`
  （60% 为示例值，按实测分布调整；**关键是可计算、可争论**）；不满足 → 回 design 改方案（仿 semantic-dimensions 根因基线）。

### D5：runner/实验一致性——band 必须取自真实检索器
- `_compute_synonym_bands` 从"自实现 difflib 复刻"改为**实例化真实 retriever（与 nodes.py 同一工厂）**对每条同义问题 search 取 top-1 band——实验测的就是线上跑的。
- 报告配置三变量补全：`difflib/0.95-0.85/-` → `hybrid(bge-small-zh-v1.5)/hit_t-inject_t/w=0.7`。
- **近重复 hit 召回数值目标（P3）**：标定后自适应定——「近重复对 hit 数较 difflib 基线提升 ≥50%」（验收可判定，简历数字更硬）。

### D6：依赖与体积决策
- 新增 `sentence-transformers` + `torch`（~2-3GB）。懒加载：仅首次 memory 检索时 import/加载，不影响启动与 --memory off 路径。
- 首次模型下载需网络（~100MB，可走 HF 镜像）；下载后离线可用。
- **这是本 change 最大的外部成本**，apply 前需用户确认；不确认则卡在任务 0（环境准备）。

## Risks / Trade-offs

| 风险 | 对策 |
|---|---|
| torch/sentence-transformers 体积大、安装失败 | 懒加载 + 失败降级 difflib（主链路零影响）；模型下载走镜像 |
| CPU embedding 延迟 | 查询只 embed 1 条（存量写时缓存）；短句 10-50ms，相对 LLM 秒级可忽略 |
| 阈值/权重拍脑袋 | D4 离线标定脚本出分布；三变量随报告列出；同义/毒化/近重复三组对照 |
| 向量化后行为变化伤回归 | --memory off 全量 L1-L4 不回退（硬门槛）+ 同问同答 100% 不回退 + 毒化对不命中 |
| 模型版本漂移 | `embedding_model` 哈希列，变更全量失效重算 |
| 实验仍可能显示"注入 L1 增益 ≈ 0" | 预期管理：验收挂三指标（N_inject 样本量 / hit 召回 / hit 精度），不单挂 L1；LLM 无记忆 100% 是既知事实 |
| 一致性断言单测在向量化后变红 | 沿用"断言 band 分层与检索器输出一致"（不绑具体 band 值） |

## Migration Plan

1. 环境：装 sentence-transformers + torch + 下载模型；EmbeddingProvider 懒加载单测（失败降级）。
2. 硬门槛（判定式）：离线三组分布，验证 `毒化全部 < hit_t 且 ≥60% 同义注入条目 > inject_t`；不过则回 design。
3. MemoryStore 加列 + 迁移 + 惰性回填（单测）。
4. HybridRetriever + BM25 + 融合 + 精确快路径 + 降级（单测三档边界 + 毒化对）。
5. nodes.py 工厂替换 + settings 配置化。
6. 标定脚本出阈值 → 写 settings；runner 改用真实检索器 + 报告三变量。
7. exp2/exp3 重跑 + --memory off 回归 + 同问同答回归；metrics-report 更新 + 开发日志。

## Open Questions

- **embedding 来源确认**：本地 bge-small-zh-v1.5（~2-3GB 依赖）是否可接受？不可接受则改 API 方案（需重评网络依赖）。
- 融合权重 w 初值 0.7 是否合理 → 以标定脚本分布为准调整。
- 模型下载源：HuggingFace 直连 vs 镜像（huggingface.co 在国内网络稳定性）→ 任务 0 实测。
