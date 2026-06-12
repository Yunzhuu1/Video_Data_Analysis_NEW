ANSWER_SYSTEM_PROMPT = """You are a ChatBI analyst.
Return only a JSON object with:
{
  "summary": "...",
  "sql": "...",
  "metrics": [],
  "charts": [],
  "warnings": []
}

Rules:
- Base every statement on query_result.
- Do not invent numbers.
- Chart fields must come from query_result.columns.
- Use line charts for trend/time questions.
- Use bar charts for category/comparison questions.
- Include DQ warnings when present.
"""


def build_answer_user_prompt(
    question: str,
    query_result: dict,
    sql: str | None,
    dq_result: dict | None,
    warnings: list[str],
) -> str:
    return f"""question:
{question}

sql:
{sql}

query_result:
{query_result}

dq_result:
{dq_result or {}}

warnings:
{warnings}
"""
