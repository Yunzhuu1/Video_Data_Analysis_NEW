## Why

metrics-report（§5/§7）与开发日志反复钉死的瓶颈：`difflib` 字符相似度对短中文问句失效——同义集 20 条与沉淀记忆的相似度实测 0.455–0.778，**全部落在 miss 波段**（inject 带 0.85–0.95 不可达），导致注入/冷热两个实验（exp2/exp3）都因 N_inject=0 而"结论仅方向性"，记忆价值只能量化到"命中直通 + token 省 21%"。根因是语义级改写（播放量→观看量、各分类→各类别）在字面层面天然低重叠，**只有语义 embedding 能把这些改写映射到相近向量**。`Retriever` 接口已预留，`docs/记忆系统设计.md` §5.1 调研结论：本场景采用 **语义+BM25 多信号融合检索**（抄 Mem0 机制、DAIL-SQL 范式，不抄框架）。

## What Changes

- **Embedding 基础设施**（新增 `app/memory/embeddings.py`）：**外接火山方舟 doubao-embedding API**（**多模态端点** `POST /api/v3/embeddings/multimodal`，文本输入，实测 `doubao-embedding-vision-251215` 2048 维；一次调用返回 1 个 embedding，批量逐条调）；EmbeddingProvider 可注入/mock（CI 无 key 也能测）；调用失败 → 日志告警 + 自动降级 difflib；embedding 模型名+版本记录进 `embedding_model` 列（模型变更全量失效重算）。
- **HybridRetriever**（实现既有 `Retriever` 协议）：
  - ① 精确匹配快路径：`norm_question` 完全相等 → hit（score=1.0，保持"同问同答 100% 一致"确定性契约，不依赖模型）
  - ② 语义信号：query embedding vs 条目 embedding 的 cosine（LanceDB HNSW 向量索引）
  - ③ 词面信号：**LanceDB 原生 BM25 FTS**（建在 `norm_question` 上，替代自研）
  - LanceDB **hybrid 查询** = 向量 + FTS + namespace/metric 过滤一条查询 → 双阈值（hit/inject）；embedding 不可用 → 降级 `TextSimilarityRetriever`（现状行为，0.95/0.85 沿用）
  - 命中后安全网不变：catalog 校验 + `metrics_consistent` + `acceptable()` 复检
- **存储换 LanceDB**（嵌入式列式向量库，替代 SQLite JSON blob）：`memory.lance/` 单表 = `norm_question / resolved_intent / metric_codes / hit_count / last_hit_at / resolver_hash / embedding`；HNSW 向量索引 + FTS 索引 + WAL 持久化；存量 SQLite 数据导入 + 惰性回填（每 search ≤10 条）；`VectorStore` 接口抽象（`Retriever` 同源，未来可换 Qdrant）。选型矩阵与代价见 `docs/记忆系统设计.md` §5.3。
- **阈值重标定（离线脚本，可复现）**：对（同义集 20 条 vs 沉淀记忆、毒化对 点赞量/播放量、近重复对）输出 cosine+BM25 融合分布 → hit 阈值 = 「毒化对全部落于其下」的最小值；inject 阈值 = 「期望注入同义条目全部落于区间内」的最大值 → 写进 settings + design。
- **实验与报告闭环**：runner `_compute_synonym_bands` 从"自实现 difflib 复刻"改为**调真实 retriever**（实验测的就是线上跑的）；exp2/exp3 重跑，预期注入带首次可填充；`docs/metrics-report.md` 更新，报告配置三变量加 **embedding 模型名**。
- **外部依赖（运行时）**：火山方舟 `ARK_API_KEY` + 已开通的 doubao-embedding-vision 模型（多模态端点，文本输入）；成本 ≈ 0.0005 元/千 tokens（本规模总成本 <1 分钱）。
- **pip 依赖**：新增 `lancedb`（+ `pyarrow`，几十 MB）；不引入 torch/transformers、不引入向量数据库服务端（Qdrant/Milvus）。

## Capabilities

### New Capabilities
<!-- 无：记忆行为归属既有 semantic-resolution；评测归属既有 agent-eval -->

### Modified Capabilities
- `semantic-resolution`: 「语义记忆检索与写入」要求从"文本相似度双阈值"升级为"语义+词面多信号融合检索 + 重标定双阈值 + 精确匹配快路径 + embedding 不可用降级 difflib"
- `agent-eval`: 「量化指标测量/记忆行为评测」要求 band 分层取自**真实（混合）检索器**，报告配置注明检索器/阈值/embedding 模型三变量

## Impact

- **Python**：新增 `app/memory/embeddings.py`（EmbeddingProvider，httpx 调方舟 API）；`app/memory/store.py` 改 **LanceDB VectorStore**（HNSW + FTS 索引 + 迁移/回填）；`app/memory/retriever.py`（HybridRetriever 消费 LanceDB hybrid 查询，协议补 namespace）；`app/graph/nodes.py`（build_retriever/VectorStore 工厂替换）；`app/eval/runner.py`（_compute_synonym_bands 复用真实检索器 + 报告三变量）；`app/settings.py`（阈值/权重/模型名/LANCE_PATH）；`tests/`（向量三档边界、降级路径、标定脚本可复现、一致性断言不绑 band 值）。
- **依赖/凭据**：新增 `lancedb` + `pyarrow`（几十 MB）；新增 `ARK_API_KEY` 配置（settings + .env，与 DeepSeek key 并列）；需在方舟控制台开通 doubao-embedding 文本模型并取得 Model ID。
- **Java**：无改动（检索在 Python 侧）。
- **文档**：`docs/记忆系统设计.md` §5.2 已写入设计输入；`docs/metrics-report.md` 记忆价值节更新；`docs/开发日志.md` 新条目。
- **评测**：exp2/exp3 重跑（真实 LLM，~15-20 分钟）；--memory off 全量回归 L1-L4 不回退；同问同答 100% 不回退。
