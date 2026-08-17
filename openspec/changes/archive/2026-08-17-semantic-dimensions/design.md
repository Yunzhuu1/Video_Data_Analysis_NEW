## Context

真实评测 L4 dimensions 61.54%（8/13），失分 5 例（c01/c03/c07/c12/c13），两类确定性模式（非随机）：
- **漏维度**：c01"分析各分类播放量趋势"、c07"对比美食和游戏分类的播放趋势"——golden `dimensions=[category]`，实际为空（category 被当 filter 或遗漏）。
- **多维度**：c03"最近7天每天播放量"、c12"美食类视频播放量趋势"、c13"最近一周每天播放量"——golden `dimensions=[]`，实际塞入 `date`（date 是 DIMENSIONS 里的合法 code，LLM 误把它当业务维度；c12 还可能把"美食"当 dimension 而非 filter）。

根因：`SEMANTIC_SYSTEM_PROMPT` 缺"date 属于时间粒度"的显式规则，且"各分类 vs X 类"的维度/过滤判定示例不足。

## Goals / Non-Goals

**Goals:**
- L4 dimensions 61.54% → ≥85%；L2 同步 ≥70%。
- 维度抽取确定性：date 不入 dimensions、各分类→dimensions、类目限定→filters。

**Non-Goals:**
- 多指标合成、门禁规则、记忆系统、回答质量。

## 失败模式 → 修复策略 对应表（P1，待 D1 实测确认）

| 实测失败模式 | 修复手段 | 目标用例 |
|---|---|---|
| `dims=[]`，golden=`[category]`（各分类漏维度） | Prompt 各分类→dimensions（示例为主）+ D3 关键词补全（c01 确定性保障） | c01 |
| **`dims=[]` + `filters=[]`，golden=`[category]` + `filters IN`（对比类问法，无"各分类"关键词）** | **新增对比类规则：'对比/比较 A 和 B 分类' → dims=[category] + filters=[category IN (A,B)]** | **c07** |
| `dims=[date]`（date 误入维度） | Prompt date 边界 + D3 date 清洗（不强制补 granularity） | c03/c13（待实测） |
| `dims=[category]`，golden=`[]`（类目被当维度） | Prompt 类目限定→filters | c12（待实测） |

若 D1 实测发现上述四种之外的模式，先补表再定修复，不强行套用 D2/D3。

## Decisions

### D1: 根因基线 = 硬前置门槛（数据驱动，P0）
用 `--llm real --platform mock` 跑语义层评测（不耗真实执行），**产出 5 个失分用例的 actual resolvedIntent vs golden 对照表**（评测 JSON 只存 spec_score，actual intent 需单独采集）。**此步为硬门槛：D2/D3 的具体规则只有在该对照表确认失败模式后才生效**——若实测模式与下表假设不符（如 c12 实际是 dims=[category] 而非 [date]、c07 实际 filters 也缺），须先修订 D2/D3 再继续。**对比类问法（c07）为必查项**：确认 actual 的 dims 与 filters 是否同时缺失。

### D2: Prompt 规则强化（通用改善，示例是主杠杆）
注意：现有 prompt 已有"各分类的播放量 → 分类是 dimensions"规则文本，c01 仍失败——**规则文本存在 ≠ 被遵循**，正反示例（D2.5）才是主修复杠杆；c01 的确定性保障实际来自 D3 关键词补全（问题含"各分类"必然命中）。

`SEMANTIC_SYSTEM_PROMPT` 增加/强化：
1. **date 边界**："`date` 是时间维度但只用于 `time_range.granularity`（day/week/month），**禁止放入 `dimensions`**；`dimensions` 仅允许业务维度 code（category/content/creator）。"
2. **各分类→dimensions**："'各分类/按分类/每类' + 指标 → 分类进 `dimensions`（group by），不进 `filters`。"
3. **类目限定→filters**："'X 类视频/美食的/游戏的' 限定单一分类 → 进 `filters`（category=X），不进 `dimensions`。"
4. **对比类规则（新增，覆盖 c07）**："'对比/比较 A 和 B 分类' → `dimensions=[category]` **且** `filters=[category IN (A,B)]`；与规则 3 的边界：单分类限定（'美食的'）→ `filters =`，多分类对比（'A 和 B'）→ `dimensions + filters IN`。"
5. **正反示例**：补"各分类播放量趋势"（dims=[category]）、"最近7天每天播放量"（dims=[]，granularity=day）、"美食类视频播放量趋势"（filters=[category=美食]）、对比类（dims=[category] + filters IN）四条示例。

### D3: 确定性兜底（定位：已知问法模式表，非通用语义推理）
`SemanticResolver._normalize` 后加轻量后处理，本质是**针对本项目已知问法的确定性模式表**（不是通用推理），仅两类高置信模式：
- **date 清洗**：`dimensions` 含 `date` → 移除（date 由 `time_range.granularity` 表达）。**不强制补 `granularity=day`**（周粒度问题会被误伤为 day；comparator 对 granularity 为 null 本就容忍）；如需补，仅当问题含"天/每天/每日"关键词时触发。
- **各分类补全**：问题文本含"各分类/按分类/每类/各类"且 `dimensions` 为空且 `filters` 无 category → 补 `category`。
- **护栏**：仅这两类模式；不做通用补全。验证步骤：补全后全量 L1~L4 对比，若任一字段（dimensions/filters 等）相比基线回退 → 回退该规则并记录。
- **R3 备注（后续候选）**：对比类（c07）暂无 D3 确定性兜底，修复完全依赖 prompt 规则 4（LLM 行为）；"对比 X 和 Y 分类"的文本提取（两个分类名 → dims + filters IN）成本略高，本轮不做。若 D1/D4 实测发现规则 4 不稳定，再考虑作为 D3 第三模式（对照表阶段定，不预做）。

### D4: 评测验证两段式
1. `--llm real --platform mock`：语义层快速验证 dimensions 提升（L4 只看 resolvedIntent，不耗执行）。
2. `--llm real --platform real`：出 L2/L4 终值（L4 dimensions ≥85%、L2 ≥70%）。

## Risks / Trade-offs

- [date 清洗误伤：某指标真实以 date 为业务维度] → 当前 7 个指标维度均不含 date 语义（date 是时间字段），清洗安全；若未来出现则按指标字典调整。
- [各分类补全误伤：'各分类'出现在非分组语境] → 触发要求 dimensions 为空且无 category filter，仍可能误补；以 real 评测为准，回退阈值内。
- [Prompt 优化可能影响其它字段（metrics/filters）] → 全量 L1~L4 对比，任何字段回退则调整。

## Migration Plan

1. 根因基线（real+mock 评测）。
2. Prompt 规则 + 示例。
3. 确定性兜底（date 清洗 + 各分类补全）+ 单测。
4. real+mock 验证 → real+real 验证。
5. 文档 + 开发日志。
