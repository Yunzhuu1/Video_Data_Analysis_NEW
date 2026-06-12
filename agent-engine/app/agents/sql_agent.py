from typing import Any

from app.clients.llm_client import LLMClient
from app.prompts.sql import SQL_SYSTEM_PROMPT, build_sql_user_prompt


class SQLGenerationAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def generate(
        self,
        question: str,
        schema_context: str,
        hard_guard_feedback: str | None,
        execution_feedback: str | None,
        dq_feedback: str | None,
        sql_attempts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.llm_client.enabled():
            user_prompt = build_sql_user_prompt(
                question=question,
                schema_context=schema_context,
                hard_guard_feedback=hard_guard_feedback,
                execution_feedback=execution_feedback,
                dq_feedback=dq_feedback,
                sql_attempts=sql_attempts,
            )
            try:
                result = await self.llm_client.complete_json(SQL_SYSTEM_PROMPT, user_prompt)
                return self._normalize(result)
            except Exception as exc:
                return self._fallback(question, f"LLM generation failed: {exc}")

        return self._fallback(question, "LLM disabled because AI_API_KEY is not configured")

    @staticmethod
    def _normalize(result: dict[str, Any]) -> dict[str, Any]:
        sql = str(result.get("sql") or "").strip()
        if not sql:
            raise ValueError("LLM JSON response did not include sql")
        return {
            "sql": sql,
            "purpose": str(result.get("purpose") or "Answer the ChatBI question"),
            "assumptions": list(result.get("assumptions") or []),
            "expectedColumns": list(result.get("expectedColumns") or []),
        }

    @staticmethod
    def _fallback(question: str, reason: str) -> dict[str, Any]:
        if "category" in question.lower():
            sql = "SELECT date, category, total_plays FROM metric_daily ORDER BY date, category LIMIT 20"
        else:
            sql = "SELECT date, category, total_plays FROM metric_daily ORDER BY date DESC LIMIT 20"
        return {
            "sql": sql,
            "purpose": "Fallback SQL for ChatBI smoke test",
            "assumptions": [reason],
            "expectedColumns": ["date", "category", "total_plays"],
        }
