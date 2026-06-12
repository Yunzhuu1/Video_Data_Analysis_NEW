from typing import Any

from app.clients.llm_client import LLMClient
from app.prompts.answer import ANSWER_SYSTEM_PROMPT, build_answer_user_prompt


class AnswerAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def generate(
        self,
        question: str,
        query_result: dict[str, Any],
        sql: str | None,
        dq_result: dict[str, Any] | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        if self.llm_client.enabled():
            user_prompt = build_answer_user_prompt(
                question=question,
                query_result=query_result,
                sql=sql,
                dq_result=dq_result,
                warnings=warnings,
            )
            try:
                return self._normalize(
                    await self.llm_client.complete_json(ANSWER_SYSTEM_PROMPT, user_prompt),
                    sql,
                    warnings,
                )
            except Exception as exc:
                fallback = self._fallback(question, query_result, sql, warnings)
                fallback["warnings"].append(f"Answer LLM fallback used: {exc}")
                return fallback

        return self._fallback(question, query_result, sql, warnings)

    @staticmethod
    def _normalize(result: dict[str, Any], sql: str | None, warnings: list[str]) -> dict[str, Any]:
        normalized_warnings = list(result.get("warnings") or [])
        for warning in warnings:
            if warning not in normalized_warnings:
                normalized_warnings.append(warning)
        return {
            "summary": str(result.get("summary") or "No summary generated."),
            "sql": result.get("sql") or sql,
            "metrics": list(result.get("metrics") or []),
            "charts": list(result.get("charts") or []),
            "recommendations": list(result.get("recommendations") or []),
            "warnings": normalized_warnings,
        }

    @staticmethod
    def _fallback(
        question: str,
        query_result: dict[str, Any],
        sql: str | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        rows = query_result.get("rows") or []
        columns = query_result.get("columns") or []
        row_count = query_result.get("rowCount", len(rows))
        summary = f"ChatBI answered '{question}' with {row_count} result rows."
        if rows:
            preview = rows[0]
            summary += f" First row: {preview}."
        return {
            "summary": summary,
            "sql": sql,
            "metrics": _basic_metrics(columns, rows),
            "charts": _basic_charts(columns, rows),
            "recommendations": [],
            "warnings": list(warnings),
        }


def _basic_metrics(columns: list[str], rows: list[dict]) -> list[dict]:
    metrics: list[dict] = []
    if not rows:
        return metrics
    first = rows[0]
    for column in columns:
        value = first.get(column)
        if isinstance(value, (int, float)):
            metrics.append({"name": column, "value": value})
    return metrics[:5]


def _basic_charts(columns: list[str], rows: list[dict]) -> list[dict]:
    if len(columns) < 2 or not rows:
        return []
    x_field = columns[0]
    y_field = next((column for column in columns[1:] if _looks_numeric(rows, column)), None)
    if y_field is None:
        return []
    chart_type = "line" if "date" in x_field.lower() or "time" in x_field.lower() else "bar"
    return [
        {
            "type": chart_type,
            "title": f"{y_field} by {x_field}",
            "xField": x_field,
            "yField": y_field,
        }
    ]


def _looks_numeric(rows: list[dict], column: str) -> bool:
    for row in rows[:5]:
        value = row.get(column)
        if value is None:
            continue
        if isinstance(value, (int, float)):
            return True
        try:
            float(str(value))
            return True
        except ValueError:
            continue
    return False
