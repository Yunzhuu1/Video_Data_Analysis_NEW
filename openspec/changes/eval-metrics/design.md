## Context

简历需要可信量化指标。正确性/安全/历史轨迹已有数据；缺：token 成本计量、直通收益、注入泛化、冷热启动。

## Goals / Non-Goals

**Goals：** 产出可审计、可复现的指标报告（直通收益/注入收益/冷热启动/token）；每个指标对应简历叙事。
**Non-Goals：** 业务功能、向量检索、记忆淘汰、前端。

## Decisions

### D1：Token 计量——模块级 TokenMeter 单例 + runner 快照归因
- `app/clients/token_meter.py`：`TokenMeter`（prompt/completion/total/calls 累加 + snapshot/reset），模块级单例。
- `LLMClient._call`：响应 `payload.get("usage")` 记录到 meter（OpenAI 兼容零额外 API）。
- eval runner：每 case 前后 `meter.snapshot()` 差值 → `result["tokens"]`；报告聚合 token（命中 vs 未命中均值）。
- 不改 `complete_json` 签名（现有调用方零改动）；mock/replay 不记录（无真实调用），仅 real 模式有数据。
- **token 口径精确化（P2-1）**：直通只跳过**语义解析阶段**的 LLM 调用，AnswerAgent 仍调 LLM → **命中用例总 token ≠ 0**。收益指标 = 同一用例命中 vs 未命中（重复对第一/二遍）的**用例总 token 差**（≈ 被消除的解析阶段 token）；报告明确标注"解析阶段消除"而非"用例 0 token"。

### D2：同义表达问题集（N=20，分层可信）
- 文件 `app/eval/synonym_cases.yaml`：20 条，5 类变换 × 4 条：
  - 指标同义（播放量→播放数据/观看次数，点赞量→点赞数）
  - 维度同义（各分类→各类别/不同分类/按分类分组）
  - 时间同义（最近7天→过去一周/近一周，每天→按天/逐日）
  - 过滤/排名同义（美食类→美食相关，Top10→前十/最高的十个）
  - 对比/趋势同义（对比A和B的播放趋势→比较A与B的播放走势）
- 每条含 `golden_spec`（可判定）；temp=0 降方差；跑两轮取稳定，波动大则报告如实标注。
- **波段 = 实验时读检索器输出（P1 + 事实修正）**：`MemoryHit.band` 本来就由 Retriever 计算（semantic-memory 接口）。同义集 YAML **不静态标注 band**；runner 在沉淀阶段完成后，对每条同义问题执行**真实 `retriever.search(question)`，取 top-1 的 band 作为分层依据**（零偏差——分层用的就是实验时实际会发生什么）。YAML 只存 `question` + `golden_spec` + `source_case`（引用 golden case id，运行时从 store 取该条，避免复制问题文本/陈旧引用）。注：短句 2 字差即可把 ratio 压到 0.85 以下（如"播放量→播放数据"），相当部分同义变换会落 miss——运行时分层会如实反映。
- **逐条审计格式（P2-3）**：报告固定输出每条同义问题的四列表：`无记忆 intent / 有记忆 intent / golden / band`——简历"逐条可审计"的实物证据。
- **阈值标定方法论（R2，非占位值）**：每个 Retriever 实现 SHALL 提供其 band 阈值 + 标定依据，禁止拍脑袋占位。标定方法示例：hit 阈值 = "已知相似反例对（如毒化对"点赞量 vs 播放量"）全部落在 hit 之下"的最小值；inject 阈值 = "期望注入的同义条目全部落在 inject 区间"的最大值。面试可讲"为什么是这个数"的方法论。
- 可信度三要素：分层覆盖、逐条可审计（四列表）、N=20 为**方向性信号（±20pp 量级，1.8σ 不构成强结论）**。

### D3：三个量化实验协议（按波段分层，人口不重叠）
- **直通收益（hit 波段）**：重复对（同一问题跑两遍）——第一遍未命中（LLM）记延迟+token，第二遍命中（直通）记延迟+token；对比延迟差与**用例总 token 差（≈ 解析阶段消除）**。只统计实际落 hit 的同义/重复条目。
- **注入收益（长尾泛化，仅 inject 波段子集，P1）**：同义集里标注为 `band=inject` 的条目，组 A（--memory off 基线）vs 组 B（--memory on，先沉淀再跑）；指标 = inject 子集 L1 口径成功率 + inject 命中率。**miss 波段子集单独报告**（反映 LLM 自身泛化，与记忆无关）；hit 波段归直通实验。三个实验人口不再重叠。
- **样本量保障（最后 review）**：沉淀后计算全量运行时 band，inject 子集 < 8 条（阈值可配）→ 报告显式标注「样本不足，结论仅方向性」；报告固定输出 N_hit/N_inject/N_miss 各波段样本量（统计卫生，让「注入实验为什么只有 X 条」可解释）。
- **冷热启动（P2-2，与实验 2 区分）**：实验 2 测**全链路**（沉淀 + 检索，写路径参与）；实验 3 测**检索侧**（预置记忆直接 seed 进 eval namespace，消除写路径方差）——冷（空）vs 热（seed 预置）跑同义集，看检索侧收益。
- 全部用现有 `--compare` 或报告分组对比；配置注明三变量（**检索器实现 + 阈值 + embedding 模型名**，如 `difflib/0.95-0.85/-`、`vector/bge-m3/0.60-0.40`）+ llm/platform/memory/日期——否则两个 vector 版本之间也无法解释。

### D4：指标报告 `docs/metrics-report.md`
- 结构：①历史轨迹表（端到端/L1/拦截率/命中率的逐轮演进，附 commit）②正确性/安全 ③效率（延迟/token，含直通对比）④记忆价值（直通/注入/冷热，按波段分层）⑤实验协议与可复现说明 ⑥**局限说明（P3）**：单用户 demo、小样本（N=20 为方向性信号）、real 模式 token 依赖 API usage 字段、同义集人工构造——主动写局限比被动被问更有说服力。
- 每个数字标注来源（评测报告/时间戳），可直接抄进简历。

## Risks / Trade-offs

- [LLM 方差影响注入收益判断] → temp=0 + 两轮取稳 + N=20；如实标注波动。
- [token 计量仅 real 模式] → 报告注明模式；mock/replay 无 token 数据（不误导）。
- [同义集可能过拟合 golden] → 只复用 golden 的意图结构，措辞全部重写；逐条审计差异。
- [冷热启动实验耗时（多跑同义集）] → 同义集 N=20，每遍 ~1-2 分钟，可控。

## Migration Plan

1. TokenMeter + LLMClient 记录（单测：usage 解析、累加、快照）。
2. runner token 快照归因 + 报告（单测：case 前后差值）。
3. 同义集 + 实验入口（--synonym-cases / 组 A/B 运行脚本）。
4. 三个实验运行（直通/注入/冷热）+ 结果入报告。
5. docs/metrics-report.md + 开发日志。
