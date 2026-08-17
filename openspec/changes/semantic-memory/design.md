## Context

现状：每问必调 LLM → 漂移/成本/无沉淀。已有资产：`metric_definition`（catalog）、LangGraph checkpoint（SQLite 先例）、eval harness（A/B 与回归）。

## Goals / Non-Goals

**Goals：** 同问同答一致率 100%（命中路径）；重复问题延迟毫秒级、token 归零；开启记忆后 L1-L4 不回退；命中率可量化；**相似但不同语义不误命中**。
**Non-Goals：** 见 proposal 非目标列表。

## Decisions

### D1：存储——agent-engine 本地 SQLite（`memory.sqlite`，用 aiosqlite）
同 `checkpoints.sqlite` 模式（引擎自有状态文件），不违反"Python 不直连业务库"边界（该边界针对 MySQL 业务数据）。**MemoryStore 用 aiosqlite**（与 checkpointer 一致，避免同步写阻塞事件循环；aiosqlite 已是现有依赖）。MVP 单实例，Java 零改动；未来多实例替换 MemoryStore 实现即可（接口隔离）。

```sql
CREATE TABLE IF NOT EXISTS semantic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_question TEXT NOT NULL,
    resolved_intent TEXT NOT NULL,     -- JSON（含确定性兜底后的值）
    metric_codes TEXT NOT NULL,        -- JSON array：涉及指标码（catalog 校验 + metrics 一致性校验用）
    hit_count INTEGER NOT NULL DEFAULT 1,
    last_hit_at TEXT NOT NULL,
    resolver_hash TEXT NOT NULL,       -- 语义规则版本：prompt/兜底文件内容哈希（防忘 bump）
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_norm ON semantic_memory(norm_question);
```

### D2：写入路径——只写"全链路成功"
- **触发点**：ANSWER 完成后收尾钩子，`try/except` 包裹（记忆失败绝不打断主链路）。
- **条件**：`query_result.success==true` 且 `dq_feedback` 为 PASS/WARNING 且 `sql_source=="semantic"` 且 `resolved_intent` 存在。
- **内容**：只存 ResolvedIntent + metric_codes，不存 SQL。
- **去重**：同 `norm_question` upsert（更新 hit_count / last_hit_at）。
- **职责边界（P2-1，避免实现矛盾）**：写钩子**只负责新条目沉淀**（sql_source=semantic 的新 run）；**命中 run（sql_source=memory）不经过写钩子**，由命中分支直接调 `store.record_hit(entry_id)`（仅更新 hit_count/last_hit_at）。两路径分离，避免"命中 run 不满足写条件 → hit_count 永不增长"的矛盾。
- **失效机制**：
  - `metric_codes` 命中时与当前 catalog 比对，口径变更 → 删除该条；
  - `resolver_hash`（`SEMANTIC_RULES_VERSION` = prompt/兜底文件内容哈希，规则文件变更自动变化，**避免日期常量忘 bump 导致整库静默失效**）与当前不符 → 整体降级未命中（保留数据待清理）。

### D3：检索——Retriever 接口 + TextSimilarityRetriever（stdlib，双阈值保守）
- **接口**（未来 RAG 替换点）：`Retriever.search(question, limit) -> list[MemoryHit]`；`MemoryHit(entry, score, band)`。
- **规范化**：小写、去空白/全半角标点、折叠空格；保留数字（最近7天 vs 最近30天必须区分）。
- **相似度**：`difflib.SequenceMatcher.ratio()`（字符级，适合中文，零依赖确定性）。
- **阈值（保守起步，评测后调）**：`HIT ≥ 0.95`、`INJECT 0.85~0.95`（settings 可配）。**为何比原 0.9/0.75 保守**：0.9 直通对"相似但不同指标"（如"最近7天点赞量" vs "最近7天播放量"）误命中风险高，会静默产出错误指标。
- **为何不用 embedding**：ollama 已下线、DeepSeek 无 embedding API；模板量小（23 用例量级）时文本相似度足够且确定性更好。未来上千条模板加 `VectorRetriever` 同一接口。

### D4：读取路径——SEMANTIC_RESOLVE 节点改造

```text
SEMANTIC_RESOLVE
  ├─ retriever.search(norm(question))
  │   ├─ band=hit 且 catalog 校验通过 且 **metrics 一致性校验通过**（见 D4.1）
  │   │    → state.resolved_intent = 存储值；sql_source="memory"；memory_hit=True
  │   │      直接进 SQL_SYNTHESIZE（跳过 LLM）
  │   ├─ band=inject → build_semantic_user_prompt(examples=命中示例 ≤3) → LLM + 确定性兜底
  │   └─ band=miss → 现状
```

#### D4.1：命中直通前 metrics 一致性校验（防静默误命中，P1 必修）
命中直通复用历史 intent 前，做轻量校验（catalog 已在 SEMANTIC_RESOLVE 手里，零额外调用）：
- 从问题文本匹配当前 catalog 的 `metricName`（如"点赞量"→total_likes、"播放量"→total_plays）；
- 若问题文本**能**匹配到指标名，且与存储条目的 `metric_codes` 不一致 → **降级 inject/miss**（不直通）；
- 若问题文本匹配不到指标名（无法判定）→ **降级 inject**（不走直通；inject 反正要调 LLM，LLM 看到完整问题，正确性有保证）。原"放行靠 0.95 兜底"在超长问题单字差压线（40 字差 2 字指标词 ratio≈0.95）时是真实 corner，收紧成本为零。
- 目的：堵住"最近7天点赞量"误命中"播放量"记忆的静默错误。
- 命中直通仍过 `acceptable()` 语义自检（结构合法性复检）；**复检不过 → 降级 miss（走正常 LLM）**。
- 命中后合成→门禁→执行→DQ→回答全链路不变（gate 三态/HITL 安全边界不受影响）。
- **`memory_hit`/`memory_band` 加入 `traced()` 的 output_payload**（与 hard_guard/dq 字段同模式，run trace 可见）。
- 命中 run 同样触发写入钩子 → 仅更新 hit_count。

### D5：few-shot 注入格式（近命中）
`build_semantic_user_prompt` 增加 `examples` 参数（question→intent，≤3 条），注入在指标字典之后、输出要求之前；只做参考，不改变输出契约。**示例选择：相似度降序 top-3，同分按 hit_count 优先**。

### D6：评测——记忆隔离 + 重复问题对 + 相似反例
- **回归隔离（硬门槛）**：`runner --memory off|on`，默认 **off**。回归评测（golden cases 全量）关闭记忆——防止记忆掩盖解析回归。
- **`--memory on` 用独立记忆库**（`:memory:` 或临时文件，跑完即弃）：防止 golden cases 记忆残留导致下次评测全部命中、掩盖真实解析（P1 必修）。
- **重复问题对用例**（--memory on 专用）：同一 question 连续跑两遍，断言第二遍 `memory_hit=true` 且 resolvedIntent 与第一遍逐字段一致。**一致率口径：只统计"两遍都成功解析"的对**（任一遍失败/未写记忆的不计入，避免 LLM 抖动拖低指标）。
- **相似反例用例**：库里只有"最近7天播放量"时，`"最近7天点赞量"` **不得命中**（band != hit）——验证 metrics 一致性校验（P1 必修）。
- **命中率指标**：`aggregate()` 增加 `memory_hit_rate`（hit run / 总 run）与 `memory_inject_rate`；报告并列展示。**直通与 few-shot 指标分开**：直通看一致率/延迟/token 归零，few-shot 看命中率 + L1-L4 不回退。
- **测试隔离**：conftest 强制 `memory_db_path=":memory:"`。
- **A/B**：基线（--memory off）vs 实验（--memory on + 重复对），`--compare` 对比 L1-L4 不回退 + 命中率/延迟。

## Risks / Trade-offs

| 风险 | 对策 |
|---|---|
| 记忆掩盖解析回归 | 回归评测默认 --memory off（D6 硬门槛） |
| 相似但不同语义误命中 → 静默错指标 | **metrics 一致性校验（D4.1）+ 阈值 0.95 保守 + 相似反例评测（D6）** |
| 陈腐模板（口径变更） | metric_codes catalog 校验 + 命中删除（D2） |
| resolver_version 忘 bump → 整库静默失效 | **内容哈希（D2）**：规则文件变更自动失效，无需手动维护 |
| 记忆污染（失败查询被沉淀） | 只写全链路成功（D2） |
| 记忆失败影响主链路 | 写入/检索全 try/except，仅告警 |
| 评测记忆残留污染 | --memory on 用独立库（D6） |
| 测试互相污染 | conftest :memory: 隔离（D6） |

## Migration Plan

1. MemoryStore + 写入钩子 + catalog/哈希校验（单测）。
2. Retriever 接口 + TextSimilarityRetriever（单测三档边界 + 指标反例）。
3. 读取路径 A：缓存直通 + metrics 一致性校验 + memoryHit/band 观测（单测：命中跳过 LLM、指标不一致降级、catalog 失效）。
4. 读取路径 B：few-shot 注入 + prompt 改造（单测）。
5. 评测（--memory 开关、独立库、重复对、相似反例、命中率）+ 全量回归 + 真实评测 + 文档。

## Open Questions

- 0.95/0.85 阈值是否合适 → 以真实评测命中率 + 相似反例通过为准调整。
- few-shot 上限 3 条 → 观察 prompt 长度与解析效果。
- metrics 一致性校验的匹配器（catalog metricName 最长前缀匹配）精度 → 反例评测验证。
