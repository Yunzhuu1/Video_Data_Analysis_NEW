"""语义解析 Prompt：LLM 只做指标/维度匹配，不写 SQL。"""

import json


def _dimension_list(value: object) -> list:
    """兼容 list 与 JSON 字符串两种 dimensions 形态（mock 为 list，真实平台为字符串）。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return []
    return list(value or [])

SEMANTIC_SYSTEM_PROMPT = """你是一个指标语义解析器。基于给定的指标字典和维度清单，把用户问题解析为结构化 JSON（ResolvedIntent）。

只允许输出 JSON 对象，格式：
{
  "intent": "aggregate | trend | ranking | detail",
  "metrics": ["metric_code"],
  "dimensions": ["dimension_code"],
  "time_range": {"type": "none | relative | absolute", "relative": {"amount": 7, "unit": "day"}, "absolute": {"start": "2023-10-01", "end": "2023-10-07"}, "granularity": "day | week | month | null"},
  "filters": [{"field": "category", "op": "=", "value": "美食"}],
  "ordering": {"field": "total_plays", "direction": "desc", "limit": 10},
  "confidence": 0.9,
  "coverage": "full"
}

规则：
- metrics 只能使用指标字典中的 metricCode；dimensions 只能使用维度清单中的维度。
- **date 是时间维度，但只用于 time_range.granularity（day/week/month），禁止放入 dimensions；dimensions 仅允许业务维度 code（category/content/creator）。**
- **'各分类/按分类/每类/各类' + 指标 → 分类进 dimensions（group by），不进 filters。**
- **'X 类视频/美食的/游戏的' 限定单一分类 → 进 filters（category=X，op= ），不进 dimensions。**
- **'对比/比较 A 和 B 分类' → 多分类对比：dimensions 含 category 且 filters 含 category IN (A,B)；区别于单分类限定的 filters =。**
- **数值过滤**：'超过/高于/大于/不低于/低于/不超过/至多' + 指标值 → filters 含该指标 code + op（>、>=、<、<=），如 完播率超过50% → {field: completion_rate, op: >, value: 50}；该过滤由下游合成器生成聚合后的 HAVING；仅维度字段（category/content/creator/date）的值过滤用 =/in/between。**
- '趋势/变化/每天' → intent=trend；'对比/各分类' 带时间 → trend；'Top/最高/前N' → ranking；'明细/列表' → detail。
- 相对时间（最近7天/上周）→ time_range.type=relative；明确日期 → absolute。
- 用户未提及时间范围时，time_range.type=none，禁止默认添加时间窗（如'最近7天'）；趋势类问题同样适用。
- 无法确定指标或维度时，confidence 给低值（< 0.5）并设置 coverage。
- 不要输出任何 SQL。

示例：
- "分析各分类播放量趋势" → intent=trend, metrics=[total_plays], dimensions=[category], filters=[], time_range={type:none, granularity:day}
- "最近7天每天播放量是多少" → intent=trend, metrics=[total_plays], dimensions=[], filters=[], time_range={type:relative, relative:{amount:7, unit:day}, granularity:day}（date 不入 dimensions）
- "美食类视频播放量趋势" → intent=trend, metrics=[total_plays], dimensions=[], filters=[{field:category, op:=, value:美食}], time_range={type:none, granularity:day}
- "完播率超过50%的创作者" → intent=aggregate, metrics=[completion_rate], dimensions=[creator], filters=[{field:completion_rate, op:>, value:50}], time_range={type:none, granularity:null}
- "对比美食和游戏分类的播放趋势" → intent=trend, metrics=[total_plays], dimensions=[category], filters=[{field:category, op:in, value:[美食,游戏]}], time_range={type:none, granularity:day}
"""


def build_semantic_user_prompt(question: str, catalog: list[dict], dimensions: list[dict],
                              examples: list[tuple[str, dict]] | None = None) -> str:
    metric_lines = "\n".join(
        f"- {m.get('metricCode')} | {m.get('metricName')} | {m.get('businessDefinition')}"
        f" | 维度: {','.join(_dimension_list(m.get('dimensions')))}"
        for m in catalog
    )
    dim_lines = "\n".join(
        f"- {d['code']} | {d['name']} | {d.get('description', '')}"
        for d in dimensions
    )
    examples_text = ""
    if examples:
        lines = ["参考示例（仅作参考，仍须按契约输出 ResolvedIntent）："]
        for q, intent in examples[:3]:
            lines.append(f"- 问题：{q}")
            lines.append(f"  意图：{json.dumps(intent, ensure_ascii=False)}")
        examples_text = "\n".join(lines) + "\n\n"

    return f"""用户问题：
{question}

指标字典：
{metric_lines or '(空)'}

维度清单：
{dim_lines or '(空)'}

{examples_text}请输出 ResolvedIntent JSON。
"""
