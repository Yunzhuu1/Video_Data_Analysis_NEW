from typing import Any

from app.clients.llm_client import LLMClient
from app.prompts.semantic import SEMANTIC_SYSTEM_PROMPT, build_semantic_user_prompt


class SemanticResolver:
    """把自然语言解析为结构化 ResolvedIntent（LLM 只做语义匹配，不写 SQL）。"""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    async def resolve(
        self,
        question: str,
        catalog: list[dict[str, Any]],
        dimensions: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not self.llm_client.enabled():
            return None
        user_prompt = build_semantic_user_prompt(question, catalog, dimensions)
        try:
            result = await self.llm_client.complete_json(SEMANTIC_SYSTEM_PROMPT, user_prompt)
            return self._normalize(result)
        except Exception:  # noqa: BLE001 - fallback to raw SQL generation
            return None

    @staticmethod
    def _normalize(result: dict[str, Any]) -> dict[str, Any]:
        """Normalize LLM output into the ResolvedIntent contract."""
        return {
            "intent": str(result.get("intent") or "aggregate"),
            "metrics": [str(m) for m in (result.get("metrics") or [])],
            "dimensions": [str(d) for d in (result.get("dimensions") or [])],
            "time_range": result.get("time_range") or {"type": "none", "granularity": None},
            "filters": result.get("filters") or [],
            "ordering": result.get("ordering"),
            "confidence": float(result.get("confidence") or 0.0),
            "coverage": str(result.get("coverage") or "partial"),
        }
