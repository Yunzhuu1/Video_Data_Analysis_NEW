SQL_SYSTEM_PROMPT = """You are a senior MySQL Text2SQL engineer.
Return only a JSON object with:
{
  "sql": "...",
  "purpose": "...",
  "assumptions": [],
  "expectedColumns": []
}

Rules:
- Generate SELECT only.
- Use only tables and columns from schema_context.
- Prefer metric_daily for aggregate trend queries.
- Add LIMIT for detail table queries.
- Add time filters when the question implies a time range.
- If previous feedback exists, fix the SQL according to that feedback.
"""


def build_sql_user_prompt(
    question: str,
    schema_context: str,
    hard_guard_feedback: str | None,
    execution_feedback: str | None,
    dq_feedback: str | None,
    sql_attempts: list[dict],
) -> str:
    return f"""question:
{question}

schema_context:
{schema_context}

hard_guard_feedback:
{hard_guard_feedback or "NONE"}

execution_feedback:
{execution_feedback or "NONE"}

dq_feedback:
{dq_feedback or "NONE"}

previous_sql_attempts:
{sql_attempts[-3:]}
"""
