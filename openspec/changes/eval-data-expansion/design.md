## Context

现状：评测样本小（golden 25 / 同义集 20），同义集全为"易层"改写（exp2 组 A L1=100%），注入增益不可量化。`spec/agent-eval` 已有「量化指标测量」（token/同义集注入/冷热/标定）。本 change 是纯评测数据 + 难度分层方法论，不动架构/库/Java。

## Goals / Non-Goals

**Goals：**
- golden cases 25→45，覆盖多指标/多条件/排名+时间/跨表/长尾歧义，出 **N=45 基线**（简历可信数字）。
- 同义集加"难层"（15 条），以**客观标准**（组 A L1<100%）筛选真错项，让注入增益可量化（>0 或诚实报告 0）。
- 报告按难度分层（easy/hard），评测严谨性可追溯。

**Non-Goals：**
- 结果级评测（`expected_result` 断言、种子数据扩展）——独立 change `eval-result-grading`。
- 数据库/schema/Java 改动。
- 指标字典扩展（语义层范畴）。
- 修改既有 25 个 golden 的 golden_spec（保持基线可比）。

## Decisions

### D1：新 golden cases 构造规范
- 分类矩阵：每个新用例标注 `category`（multi_metric / multi_filter / ranked_time / cross_table / longtail_ambiguous），`difficulty`（normal / hard）。
- **先真实 LLM 探测定稿**：候选用例先跑 `--llm real --platform mock`，LLM 能稳定解析出与 golden_spec 一致 → 定稿；反复漂移的歧义题 → 归入 longtail 且 golden_spec 按"可判定"原则调整（歧义题可不标 golden_spec，仅端到端统计——沿用既有规则）。
- 覆盖校验（沿用 test_synonym_cases 模式）：每个新 case 的 golden 指标必须都在 metric_catalog 中。
- **已知边界（P2-2）**：multi_metric 用例（"播放量+点赞量同查"）会固定走降级路径——合成器为 v1 单指标（`synthesize()` 对 `len(metrics)!=1` 抛 `SynthesisError` → raw LLM，`sql_source=fallback`）。L1-L4 不受影响（比的是 resolvedIntent），但报告应注明"multi_metric 用例 sql_source=fallback 属预期"；这也提示**多指标合成**是现成的后续 change 素材。

### D2：难层定义与客观筛选（核心方法论）
- **定义（P1 修订，双重条件）**：难层有效条目 = **组 A L1<100%** 且 **当前检索器 band=inject**（对 source 的融合分 ≥ inject_t）。只看"组 A 错"不够——**band=miss 的难层条目组 B 根本不会有示例注入**（注入路径只在 inject 带触发），会产出无法归因的"hard 增益=0"（eval-metrics P1 的复现）。
- **流程**：构造候选难层（15-25 条）→ 组 A（--memory off）真实跑 **+ 运行时 band 计算**（与线上同一检索器，复用 `_compute_synonym_bands`）→ `hard_layer_filter.py` 输出三列判定表（**组 A L1 / band / 判定**）→ 真难层 = `组A错 且 band=inject` → 组 B 跑真难层子集 → 对比注入增益。
- **分层归属**：`组A错 且 band=inject` → **真难层**（注入实验统计口径）；`组A错 且 band=miss` → **miss 泛化层**（语义距离超出注入可达范围，属 LLM 自身泛化，单独报告，不并入注入增益）。
- **判定式**：难层有效 = `∃ 难层条目: 组A L1=0 且 band=inject 且 组B L1=1`（注入示例把错掰对）；若真难层组 A 仍 100% 或 band 全 miss → 诚实报告"注入在该难度层无增益/不可达"，不硬凑。
- **最小声明口径（P3）**：报告固定展示逐例翻转明细（组A intent / 组B intent / golden / band 四列），最小声明 = "至少 1 例翻转"，不宣称"显著提升"（N=8 时 1 例 ≈ 12.5pp，统计上仅方向性）。
- **防过拟合**：难层条目只复用 golden 的意图结构，措辞全部重写；不与既有易层重复。

### D3：difficulty 分层与报告口径
- `synonym_cases.yaml` 每条加 `difficulty: easy|hard`（易层沿用既有 20 条标 easy）。
- runner 实验报告按难度分组输出：`easy: N / L1 组A / L1 组B / 增益`；`hard（真难层，band=inject）: N / ...`；`miss 泛化层: N / 组A L1`（单独报告，不并入注入增益）。
- metrics-report 增加"N=45 基线"与"难度分层注入收益"小节，含逐例翻转四列表与最小声明口径。

### D4：与既有评测兼容（零破坏）
- 不改既有 golden_spec 与断言逻辑；新增用例走同一 `evaluate_case` + `compare_spec`。
- `DEFAULT_CASES` 指向同一 cases.yaml，无需改路径；runner 增加 difficulty 透传（默认无 difficulty 视为 normal）。
- **回归门槛（P2-1，子集对比口径）**：N=45 全量 --memory off 跑后，**既有 25 例**在 N=45 评测中的 L1-L4 与 N=25 基线一致（同分布子集对比，这是"不回退"的可辩护结论）；**N=45 整体（含 20 个更难新用例）单独报告**，不与 N=25 直接比。

## Risks / Trade-offs

| 风险 | 对策 |
|---|---|
| 新增用例难产/LLM 解析不稳定 | 探测定稿流程（D1）；歧义题不标 golden_spec 只走端到端 |
| 难层候选全被 LLM 秒杀（组 A 仍 100%） | 判定式不硬凑，诚实报告 0 增益；扩大候选池再筛 |
| 难层条目 band=miss（注入不可达）导致增益 0 无法归因 | D2 双重条件：band=inject 才算真难层；miss 泛化层单独报告（P1） |
| 样本扩大后 L1-L4 数字波动（含 LLM 方差） | 报告注明 N 与运行次数；与 N=25 基线同分布对比 |
| 难层过拟合 golden | 措辞全重写 + 与易层去重（D2 防过拟合） |

## Migration Plan

1. 数据扩展：cases.yaml +20（按 D1 分类矩阵 + 探测定稿）；synonym_cases.yaml +15 难层（difficulty 字段）。
2. runner 适配：difficulty 透传 + 按难度分层报告。
3. 难层筛选脚本 `app/eval/hard_layer_filter.py`：组 A 跑候选难层 → 输出真错项清单（可复现）。
4. 实验：N=45 全量 --memory off 基线 + --memory on 难层注入实验（真实 LLM）。
5. 报告：metrics-report 更新（N=45 基线 + 难度分层注入收益）；开发日志。

## Open Questions

- 新 golden 用例的具体清单（构造时先列 25 候选 → 探测定稿 → 收敛到 20）。
- 难层候选池规模（先 20-25 条 → 筛选后保留 ≥8 条真难层才有统计意义，否则并入诚实报告）。
- 报告是否新增"难度分层"为固定输出（倾向是，成本低）。
