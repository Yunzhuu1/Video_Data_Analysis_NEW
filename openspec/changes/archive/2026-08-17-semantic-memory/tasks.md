## 1. MemoryStore + 写入路径

- [x] 1.1 memory.sqlite 建表 + MemoryStore（upsert/查询/删除），单测
- [x] 1.2 写入钩子：全链路成功才写（query_result.success + DQ PASS/WARNING + sql_source=semantic），try/except 隔离
- [x] 1.3 catalog 校验 + resolver_hash（内容哈希）失效机制，单测（口径变更→删除；哈希不符→降级）

## 2. Retriever

- [x] 2.1 Retriever 接口 + MemoryHit（score/band）
- [x] 2.2 TextSimilarityRetriever：规范化 + SequenceMatcher + 双阈值 0.95/0.85，单测三档边界
- [x] 2.3 metrics 一致性校验：问题文本匹配 catalog metricName → 与存储 metric_codes 比对，不一致降级

## 3. 读取路径 A（缓存直通）

- [x] 3.1 SEMANTIC_RESOLVE 记忆前置：hit → 复用 intent + sql_source=memory + memory_hit/band 标记
- [x] 3.2 state.py sql_source 增 memory；schemas.py/AnalyzeResponse 增 memoryHit/memoryBand 透传
- [x] 3.3 单测：命中跳过 LLM（mock 验证未调用）、metrics 不一致降级、acceptable() 复检、catalog 失效

## 4. 读取路径 B（few-shot 注入）

- [x] 4.1 build_semantic_user_prompt 支持 examples 参数（≤3 条 question→intent）
- [x] 4.2 inject 分支接入 + 单测（注入内容/格式/不改变输出契约）

## 5. 评测与回归

- [x] 5.1 runner --memory off|on（默认 off）；**--memory on 用独立记忆库（:memory:/临时文件）**；conftest :memory: 隔离
- [x] 5.2 重复问题对用例（一致率 100%，口径=两遍都成功）+ 相似反例用例（点赞量不命中播放量）+ memory_hit_rate/inject_rate 指标
  - **用例 schema**：cases.yaml 用 `repeat_of: <case_id>`（重复对）与 `setup_question`（反例预置，写库后查）表达
  - **模式适用性（P2-2）**：mock 模式 LLM 关闭 → 解析返回 None → 写入不触发 → **重复对/反例仅适用 replay/real 模式**；mock/CI 覆盖靠单测（2.3/3.3）
- [x] 5.3 Python pytest + ruff 全绿
  - 实测：80/80、ruff clean
- [x] 5.4 真实评测：--memory off 全量回归（L1-L4 100% 不回退）→ --memory on 重复对/反例（一致率 100%、反例不命中、命中率/延迟/token 对比）
  - 实测：--memory off 回归 L1/L2/L3 100%、命中率 0（隔离生效）；--memory on 聚焦冒烟 c24 重复对 PASS（第二遍命中）、c25 反例不命中、hit_rate 可见
  - 已知限制：real 模式反例 seeding 写入 runner 本地 store 而非服务器 store（c25 变相空测，逻辑由单测覆盖）；--memory on 全量 25 条需独立 MEMORY_DB_PATH 服务端配置
  - **服务器配置（P3）**：--memory on real 评测需服务器启动时 `MEMORY_DB_PATH=eval-memory.sqlite` 且**跑前删除**旧库
- [ ] 5.5 更新 docs/开发日志.md（AGENTS.md 语义解析说明如需同步）
