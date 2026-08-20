## Why

scale-data（C1）扩大了数据模型后，两个**生产级查询能力缺口**更明显（demo 一查就露馅）：
1. **数值过滤**：合成器不支持"完播率 > 50% 的创作者"这类**指标值过滤**（生产最常见）；只支持维度值过滤（WHERE category=美食）。
2. **跨源多指标**：n02「各分类的完播率和互动率」固定降级 raw SQL（completion_rate 在 play_detail、engagement_rate 在 fact）——新数据模型下这类"跨表收益/比率"组合查询更多。

这是"能力补全"，让规模扩展后的数据真正可查（A+B 组合里缺失的 B）。

## What Changes

### 模块 1：指标值过滤（HAVING）
- `ResolvedIntent.filters` 扩展 op：`>`、`>=`、`<`、`<=`（现有 `=`/`in`/`between` 保留）。
- **区分维度过滤 vs 指标过滤**：field 是维度（category）→ WHERE；field 是指标（completion_rate）→ **HAVING**（聚合后过滤）。
- 合成器：`_filter_cond` 生成 HAVING 条件（聚合表达式 = 指标公式）；无 GROUP BY 的聚合同样适用（MySQL HAVING 无 GROUP BY 等价 WHERE 聚合）。
- LLM prompt：教它解析"超过/高于/低于 N" → 指标过滤（op >/<）；`_acceptable_intent` 与比较器同步支持新 op。

### 模块 2：跨源多指标（n02 解锁）
- 合成器支持**同粒度跨源多指标**：不同 sourceTable 的指标，若共享同一 group-by 集（date/category 等）且时间/过滤一致 → **分别聚合子查询 + JOIN**（按维度键对齐）。
- 约束（防错）：跨源多指标**必须共享 dims/time/filters/ordering**；粒度不对齐（如一个按 category、一个按 content）→ 显式降级。
- n02「各分类的完播率和互动率」从 fallback → semantic（子查询 JOIN）。
- LLM prompt：支持多指标跨源组合；比较器/评测同步。

## Capabilities

### New Capabilities
- （无新 capability——合成器/契约能力扩展，属既有语义层）

### Modified Capabilities
- `semantic-resolution`: 「SQL 由确定性合成器生成」扩展——指标值过滤（HAVING）与同粒度跨源多指标（子查询 JOIN）。
- `agent-eval`: 评测数据覆盖补数值过滤/跨源多指标用例（n02 解锁、新增数值过滤用例）。

## Impact

- `agent-engine/app/synthesis/sql_synthesizer.py`：_filter_cond（HAVING）、跨源多指标（子查询 JOIN）。
- `agent-engine/app/agents/semantic_resolver.py` + `app/prompts/semantic.py`：新 op 解析、跨源多指标。
- `agent-engine/app/graph/state.py`：filters op 类型扩展（如无则）。
- `agent-engine/app/eval/cases.yaml`：数值过滤用例（~4）+ n02 预期改 semantic。
- 单测 + `docs/metrics-report.md` + `docs/开发日志.md`。
- Java：无改动。
