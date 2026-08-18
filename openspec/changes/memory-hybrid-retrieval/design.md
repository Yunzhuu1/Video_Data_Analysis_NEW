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
- 独立向量数据库服务端（Qdrant/Milvus/pgvector）、分布式/多节点：单节点嵌入式 LanceDB 已够；多实例/多租户时经 `VectorStore` 接口迁 Qdrant（见 §5.3 决策记录）。
- 自建索引库（FAISS 等）：LanceDB 已内置 HNSW/IVF-PQ + BM25 FTS，不自造轮子。
- 多用户/多租户记忆、记忆淘汰策略（仅沿用 hit_count/last_hit_at 排序）。
- AST 骨架相似度（DAIL-SQL 第二维，属模板提炼 change，后续）。
- 指标别名表（语义层范畴，后续 change）。

## Decisions

### D1：Embedding 来源——火山方舟 doubao-embedding API（多模态端点 + 文本输入）+ 降级兜底
- **选**：外接火山方舟**多模态向量端点** `POST /api/v3/embeddings/multimodal`（实测可用：账号开通的是 `doubao-embedding-vision-251215`，2048 维；`/api/v3/embeddings` 文本端点对 text 模型 404——账号未开通）。`EmbeddingProvider` 用 httpx 封装（**embedding 侧零新增依赖**，httpx 已有；存储侧 lancedb 见 D3/D6）。
- **调用语义（实测确认）**：多模态端点 `input` 列表 = **单文档的多模态内容**（text/image/video 组合），**一次调用返回 1 个 embedding**——批量文本需逐条调用（EmbeddingProvider 内部 for 循环）。
- **base URL 容错**：`ARK_BASE_URL` 允许带或不带 `/api/v3` 后缀，代码归一化（`re.sub(r'/api/v3$', '', base)`）。
- **替代考虑**：① 本地 bge-small-zh（sentence-transformers+torch）→ ~2-3GB 依赖，被 API 取代；② 纯 BM25/词级 → 分不开同义改写；③ 不升级 → 注入实验永久空转。
- **为何 API 而非本地**：国内北京 region 网络最稳；成本 ≈0.0005 元/千 tokens（本规模 <1 分钱）；绕开 torch/transformers；文档支持稀疏向量（后续可作词面信号升级，见 D2）。
- **可注入/mock**：`EmbeddingProvider` 定义 `embed(question) -> list[float] | None`，测试注入固定向量（CI 无 key 可跑）。
- **调用失败降级**：embed 返回 None/抛错 → 仅告警，检索降级 `TextSimilarityRetriever`（0.95/0.85）——不打断主链路。
- **模型版本**：`embedding_model` 列存 Model ID + 配置哈希，模型变更 → 全量失效重算。
- **确定性注意（实测）**：同文本两次 cos≈0.999（非严格 1.0）——命中路径靠"精确匹配快路径"（norm 相等）保 100% 契约，不依赖 embedding；embedding 只用于近重复/语义改写候选。

### D2：检索架构——三层混合 HybridRetriever（实现既有 Retriever 协议）
```
search(question, namespace)
  ├─ ① 精确匹配快路径：norm_question 完全相等 → hit（score=1.0）
  │     确定性契约（同问同答 100%）不依赖模型，模型漂移不影响
  ├─ ② 语义信号：query embedding vs 条目 embedding 的 cosine（LanceDB 向量索引）
  ├─ ③ 词面信号：LanceDB 原生 BM25 FTS（FTS search，建在 norm_question 上，替代自研）
  │     ②③ 分开查询（各自 search），融合按 D4 公式自算：score = w·cos_norm + (1−w)·bm25_norm
  └─ 双阈值（hit ≥ hit_t / inject ≥ inject_t）→ 同现状 band 语义
```
- **替代考虑**：纯向量 → 可能漏精确词匹配（"最近7天"这类字面关键）；纯 BM25 → 漏语义改写。融合是 Mem0 multi-signal 的落地形态。
- **词面信号为何用 LanceDB FTS 而非自研**：① 引擎原生 BM25，省掉自研任务与维护；② **与向量分开查询（各自 search），融合由我们按 D4 公式自算，保留 w 控制——不消费引擎融合分（"抄机制不抄框架"，P1 路径 B）**；③ 中文按字级切分与自研字二元组同量级，且支持后续换 tokenizer/接 sparse。
- 命中后安全网不变：`_catalog_valid` + `metrics_consistent` + `_acceptable_intent` 复检。
- **inject 示例的意图一致性（P2-2）**：语义相似 ≠ 意图相同（"各分类播放量排名"=ranking vs "各分类播放量趋势"=trend，cosine 很高）。`metrics_consistent` 只保护 hit 路径，inject 路径无一致性防护。策略：**注入示例按 intent 去重**（top-3 尽量覆盖不同 intent，同 intent 只取相似度最高一条）+ **报告记录注入示例的 intent 分布**（可审计，防负迁移）。

### D3：存储——LanceDB 本地目录（嵌入式列式 + HNSW/IVF-PQ + 原生 BM25 FTS + WAL）
- **选型**：`lancedb.connect("memory.lance")`，单表即整个记忆库；每行 = `id / norm_question / resolved_intent(JSON str) / metric_codes(list) / hit_count / last_hit_at / resolver_hash / embedding_model / embedding(vector)`；namespace 作为过滤条件（不单列分区）。
- **索引**：`embedding` 建 HNSW（或 IVF-PQ）向量索引；`norm_question` 建 FTS 索引（BM25）；`namespace`/`metric_codes` 走结构化过滤。
- **写入**：upsert 同步写 embedding（写钩子路径）；`record_hit` 更新 hit_count/last_hit_at；WAL 保证崩溃安全。
- **迁移/回填**：存量 `semantic_memory` SQLite 数据导入 LanceDB；缺 embedding 条目惰性回填——**每 search 至多补算 N=10 条**（每条 API ~100-300ms，最坏 ~1-3s）；**启动时后台任务预回填**；**①精确匹配快路径在回填前即可命中**（写进报告）。
- **为何 LanceDB 而非 SQLite JSON / FAISS / Qdrant**：选型矩阵与代价见 `docs/记忆系统设计.md` §5.3——嵌入式无服务端、原生混合检索、磁盘列式 1k→百万条不迁移；分布式能力弱是已知代价，`VectorStore` 接口抽象保证可迁 Qdrant。

### D4：融合评分与阈值重标定（离线脚本，可复现）
- **评分来源（P1，2026-08-18 定死为路径 B，禁止"或"）**：**不消费 LanceDB 引擎的 hybrid 融合分**——LanceDB 只当"向量索引 + FTS 检索器"用（向量 search 与 FTS search 分开查），**融合由我们自己按 D4 公式算**。理由：①保留 w 权重控制（报告三变量含 w）；②与标定脚本公式一致，可复现；③"抄机制不抄框架"哲学的延续。
- **标定公式（P2-1，归一化写死，保证可复现）**：
  - `cos_norm = max(0.0, cos)`（cosine ∈ [-1,1] 裁剪到 [0,1]）
  - `bm25_norm = bm25_score / top1_bm25_score`（候选集内除以最高分 → [0,1]；BM25 无界，用候选集内相对分）
  - `score = w·cos_norm + (1−w)·bm25_norm`（w 初值 0.7，标定后定）
- **FTS 质量兜底（P3 确认）**：即使 LanceDB FTS 对中文切分不佳，BM25 只是辅信号（w=0.7 语义为主），最坏情况 hybrid 退化为准纯向量——可存活；task 1.2 验证 + 回退自研 BM25/sparse 已覆盖。
- **标定方法**（沿用 design 既有方法论，落地为脚本 `app/eval/calibrate_thresholds.py`）：
  - hit 阈值 = 「毒化对（点赞量 vs 播放量）全部落在 hit 之下」的最小值
  - inject 阈值 = 「期望注入的同义条目全部落在 inject 区间」的最大值
  - 输出三组分布表（同义集 20 条 / 毒化对 / 近重复对）→ 定阈值与 w → 写 settings + 报告
- **硬门槛（先验证后实现，判定式可执行——P1，2026-08-18 实测修订）**：
  - **实测发现**：毒化对"播放量 vs 点赞量"仅一字之差，cosine=0.812 高于 8/20 条同义对（min 0.703）——**任何相似度都无法把"一字差的指标对"从语义改写中分离**，原判据"毒化对全部 < hit_t"结构性不可满足。
  - **修订判定式**：`近重复（一字微调）≥ hit_t（≈0.95，实测 0.989）` 且 `≥60% 同义注入条目 ≥ inject_t（≈0.80，实测 14/20=70%）`；**毒化保护由 `metrics_consistent`（catalog 校验）承担**（c25 反例功能单测，非相似度层）。
  - 不满足 → 回 design 改方案（仿 semantic-dimensions 根因基线）。

### D5：runner/实验一致性——band 必须取自真实检索器
- `_compute_synonym_bands` 从"自实现 difflib 复刻"改为**实例化真实 retriever（与 nodes.py 同一工厂）**对每条同义问题 search 取 top-1 band——实验测的就是线上跑的。
- **降级可观测性（P2-2）**：真实实验（--memory on + real）先探测 EmbeddingProvider 可用性；不可用 → 实验标记 **DEGRADED**，报告显式标注"本实验以 difflib 降级运行，N_inject=0 不代表混合检索失败"——防止"N_inject=0"被误读为"混合检索分不开"。
- 报告配置三变量补全：`difflib/0.95-0.85/-` → `hybrid(doubao-embedding-<model>)/hit_t-inject_t/w=0.7`。
- **近重复 hit 召回数值目标（P3）**：标定后自适应定——「近重复对 hit 数较 difflib 基线提升 ≥50%」（验收可判定，简历数字更硬）。

### D6：依赖与凭据决策
- **pip 依赖**：新增 `lancedb`（+ `pyarrow`，几十 MB）；**不引入** torch/transformers/sentence-transformers/onnxruntime、不引入向量数据库服务端（Qdrant/Milvus）、不自建索引（FAISS）。embedding 侧 httpx（已有）。
- **新增凭据/配置**：`ARK_API_KEY`（settings + .env，与 DeepSeek key 并列）+ `ARK_EMBEDDING_MODEL`（Model ID，控制台开通后填入）+ `ARK_BASE_URL`（默认 `https://ark.cn-beijing.volces.com`）+ `MEMORY_LANCE_PATH`（默认 `memory.lance/`）。
- **CI/测试隔离**：EmbeddingProvider 可 mock（固定向量），向量单测不依赖真实 API；标定脚本与真实实验在本地/显式命令下才调 API。
- **外部成本**：需用户控制台开通 doubao-embedding 文本模型并创建 API Key（一次性）；调用成本本规模可忽略。

## Risks / Trade-offs

| 风险 | 对策 |
|---|---|
| API embedding 依赖外部服务（网络/限流/宕机） | 国内北京 region 稳定；调用失败降级 difflib（主链路零影响）；EmbeddingProvider 可 mock |
| API 调用延迟 | 查询只 embed 1 条（存量写时缓存）；单次 ~100-300ms 相对 LLM 秒级可忽略；回填有界（≤10 条/search） |
| key 泄露/误用 | 只存本地 .env，不落库不打印；仅 agent-engine 进程读取 |
| API 计费异常 | 本规模 <1 分钱；settings 可配开关/阈值，超量可降级 difflib |
| 实验时 API 不可用 → 静默降级 difflib，N_inject=0 归因污染 | runner 先探测 embedding 可用性，不可用标 DEGRADED 并显式写入报告（P2-2） |
| LanceDB 分布式/多节点能力弱（较 Qdrant/Milvus） | 单节点定位符合现状；`VectorStore` 接口抽象 + 数据导出，多实例/多租户时迁 Qdrant（docs §5.3 触发条件明确） |
| LanceDB 相对较新（社区 < Qdrant/Milvus） | 生产在用 + pyarrow/DataFusion 生态；纳入评测回归门禁，异常可回退 difflib |
| 阈值/权重拍脑袋 | D4 离线标定脚本出分布；三变量随报告列出；同义/毒化/近重复三组对照 |
| 向量化后行为变化伤回归 | --memory off 全量 L1-L4 不回退（硬门槛）+ 同问同答 100% 不回退 + 毒化对不命中 |
| 模型版本漂移 | `embedding_model` 哈希列，变更全量失效重算 |
| 实验仍可能显示"注入 L1 增益 ≈ 0" | 预期管理：验收挂三指标（N_inject 样本量 / hit 召回 / hit 精度），不单挂 L1；LLM 无记忆 100% 是既知事实 |
| 一致性断言单测在向量化后变红 | 沿用"断言 band 分层与检索器输出一致"（不绑具体 band 值） |

## Migration Plan

1. 环境/凭据：开通方舟 doubao-embedding 文本模型 + 创建 ARK_API_KEY；EmbeddingProvider（httpx 封装）单测（mock 注入 + 失败降级）。
2. 硬门槛（判定式）：离线三组分布，验证 `毒化全部 < hit_t 且 ≥60% 同义注入条目 > inject_t`；不过则回 design。
3. LanceDB VectorStore：建表（HNSW + FTS 索引）+ 存量 SQLite 导入 + 惰性回填（单测：schema/索引/回填有界/WAL）。
4. HybridRetriever：LanceDB 向量 search + FTS search 分开查 + D4 自算融合 + 精确快路径 + 双阈值 + 降级 difflib（单测三档边界 + 毒化对）。
5. nodes.py 工厂替换 + settings 配置化。
6. 标定脚本出阈值 → 写 settings；runner 改用真实检索器 + 报告三变量。
7. exp2/exp3 重跑 + --memory off 回归 + 同问同答回归；metrics-report 更新 + 开发日志。

## Open Questions

- **端点/模型已确认（实测）**：多模态端点 `/api/v3/embeddings/multimodal` + `doubao-embedding-vision-251215`（2048 维）；账号未开通文本模型（text 端点 404）。
- **存储已定 LanceDB**（docs §5.3 决策记录）；待实测确认：LanceDB 中文 FTS 切分质量是否够（不够则回退自研 BM25 或接 sparse）。
- **词面信号**：默认消费 LanceDB 原生 BM25 FTS；火山方舟 API 原生稀疏向量（sparse_embedding）作为后续可选项（模型级质量，需验证与 dense 的同模型一致性）。
- **key 获取**：用户在方舟控制台开通模型 + 创建 API Key（`ARK_API_KEY`），apply 前提供。
- 融合权重 w 初值 0.7 是否合理 → 以标定脚本分布为准调整。
