"""语义解析 Prompt：LLM 只做指标/维度匹配，不写 SQL。"""

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
- 语义判断：'各分类的播放量' → 分类是 dimensions（group by）；'美食类视频的播放量' → 美食是 filters（where）。
- '趋势/变化/每天' → intent=trend；'对比/各分类' 带时间 → trend；'Top/最高/前N' → ranking；'明细/列表' → detail。
- 相对时间（最近7天/上周）→ time_range.type=relative；明确日期 → absolute。
- 无法确定指标或维度时，confidence 给低值（< 0.5）并设置 coverage。
- 不要输出任何 SQL。
"""


def build_semantic_user_prompt(question: str, catalog: list[dict], dimensions: list[dict]) -> str:
    metric_lines = "\n".join(
        f"- {m.get('metricCode')} | {m.get('metricName')} | {m.get('businessDefinition')}"
        f" | 维度: {','.join(m.get('dimensions') or [])}"
        for m in catalog
    )
    dim_lines = "\n".join(
        f"- {d['code']} | {d['name']} | {d.get('description', '')}"
        for d in dimensions
    )
    return f"""用户问题：
{question}

指标字典：
{metric_lines or '(空)'}

维度清单：
{dim_lines or '(空)'}

请输出 ResolvedIntent JSON。
"""
