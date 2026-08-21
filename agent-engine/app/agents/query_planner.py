from __future__ import annotations

import time
from typing import Any

from app.clients.llm_client import LLMClient
from app.prompts.query_planning import (
    QUERY_PLANNING_SKILL_VERSION,
    QUERY_PLANNING_SYSTEM_PROMPT,
    build_query_planning_prompt,
)


class QueryPlannerAgent:
    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client or LLMClient()

    async def select(self, question: str, intent: dict[str, Any], candidates: list[dict[str, Any]],
                     feedback: dict[str, Any] | None = None) -> dict[str, Any]:
        prompt = build_query_planning_prompt(question, intent, candidates, feedback)
        started = time.perf_counter()
        if self.llm_client.enabled():
            raw = await self.llm_client.complete_json(QUERY_PLANNING_SYSTEM_PROMPT, prompt)
        else:
            realtime = any(word in question for word in ("实时", "最新", "刚刚", "当前"))
            ranked = sorted(candidates, key=lambda item: (
                0 if realtime and item.get("freshness") == "REALTIME" else 1,
                item.get("costTier", 99), item.get("planId", ""),
            ))
            raw = {
                "selected_plan_id": ranked[0]["planId"],
                "reason_code": "REALTIME_REQUIRED" if realtime else "LOW_COST",
                "explanation": "deterministic no-LLM fallback",
                "confidence": 1.0,
            }
        allowed = {"selected_plan_id", "reason_code", "explanation", "confidence"}
        if set(raw) - allowed:
            raise ValueError("planner returned forbidden physical fields")
        if raw.get("reason_code") not in {"LOW_COST", "REALTIME_REQUIRED", "VALIDATION_RETRY"}:
            raise ValueError("invalid planner reason_code")
        return {
            **raw,
            "skill_version": QUERY_PLANNING_SKILL_VERSION,
            "prompt_chars": len(prompt),
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
        }
