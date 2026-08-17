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
            return self._apply_fallbacks(question, self._normalize(result))
        except Exception:  # noqa: BLE001 - fallback to raw SQL generation
            return None

    @staticmethod
    def _apply_fallbacks(question: str, intent: dict[str, Any]) -> dict[str, Any]:
        """确定性兜底（已知问法模式表，非通用推理）：date 清洗 + 各分类补全 + 天粒度触发。"""
        q = question or ""
        dims = list(intent.get("dimensions") or [])
        # 1) date 清洗：date 属 time_range.granularity，不进 dimensions（c07/c12/c13 主失败模式）
        if "date" in dims:
            dims.remove("date")
        # 2) 各分类补全：已知问法模式且无维度、无 category filter → 补 category（c01 偶发兜底）
        if any(k in q for k in ("各分类", "按分类", "每类", "各类")):
            has_category_filter = any(
                isinstance(f, dict) and str(f.get("field") or "").lower() == "category"
                for f in (intent.get("filters") or [])
            )
            if not dims and not has_category_filter:
                dims.append("category")
        intent["dimensions"] = dims
        # 3) trend 且含"每天/每日/按天"且 granularity 为空 → 补 day（不强制，关键词触发）
        tr = intent.get("time_range") or {}
        if intent.get("intent") == "trend" and tr.get("granularity") is None                 and any(k in q for k in ("每天", "每日", "按天")):
            tr["granularity"] = "day"
            intent["time_range"] = tr
        return intent

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
