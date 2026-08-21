from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.lineage.catalog import load_mock_snapshot
from app.lineage.planning import PlanEnumerator, PlanValidator, route_selection


def load_lineage_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def evaluate_lineage(cases: list[dict[str, Any]]) -> dict[str, Any]:
    snapshot = load_mock_snapshot()
    enumerator = PlanEnumerator()
    validator = PlanValidator()
    path_hits = 0
    path_total = 0
    rejection_hits = 0
    rejection_total = 0
    selection_hits = 0
    selection_total = 0
    planner_invocations = 0
    details = []
    first_candidates = None
    first_intent = None
    for case in cases:
        intent = case["resolved_intent"]
        result = enumerator.enumerate(intent, snapshot)
        expected_rejection = case.get("expectedRejection")
        if expected_rejection:
            rejection_total += 1
            ok = expected_rejection in {item.code for item in result.rejected}
            rejection_hits += int(ok)
            details.append({"id": case["id"], "rejection_ok": ok,
                            "rejected": [vars(item) for item in result.rejected]})
            continue
        golden = case["golden"]
        path_total += 1
        matching = [plan for plan in result.candidates if _matches(plan, golden)]
        path_hits += int(bool(matching))
        source, selected = route_selection(result.candidates)
        if source == "PLANNER_AGENT":
            planner_invocations += 1
            selected = _directional_choice(case["question"], result.candidates).planId
        selected_path = next((p.metricPathId for p in result.candidates if p.planId == selected), None)
        if golden.get("selectedPathId"):
            selection_total += 1
            selection_hits += int(selected_path == golden["selectedPathId"])
        details.append({
            "id": case["id"], "path_ok": bool(matching), "candidate_count": len(result.candidates),
            "selection_source": source, "selected_path": selected_path,
            "rejected": [vars(item) for item in result.rejected],
        })
        if first_candidates is None and result.candidates:
            first_candidates, first_intent = result.candidates, intent
    illegal = validator.validate("forged-plan", first_candidates or [], first_intent or {}, snapshot)
    replan = validator.validate(
        (first_candidates or [None])[0].planId if first_candidates else None,
        first_candidates or [], first_intent or {}, snapshot,
    )
    return {
        "catalogVersion": snapshot["catalogVersion"],
        "path_recall": _ratio(path_hits, path_total),
        "expected_rejection": _ratio(rejection_hits, rejection_total),
        "plan_selection_accuracy": _ratio(selection_hits, selection_total),
        "illegal_plan_rejection": {"hits": int(illegal["code"] == "INVALID_PLAN_ID"), "total": 1},
        "replan_success": {"hits": int(replan["verdict"] == "PASS"), "total": 1},
        "planner_invocation_count": planner_invocations,
        "details": details,
    }


def _matches(plan, golden):
    if plan.metricPathId != golden["metricPathId"]:
        return False
    bindings = {route.bindingId for route in plan.fieldRoutes if route.bindingId}
    edges = {edge for route in plan.fieldRoutes for edge in route.edgeIds}
    return set(golden.get("bindingIds", [])) <= bindings and set(golden.get("edgeIds", [])) <= edges


def _directional_choice(question, candidates):
    realtime = any(word in question for word in ("实时", "最新", "刚刚", "当前"))
    return min(candidates, key=lambda plan: (
        0 if realtime and plan.freshness == "REALTIME" else 1,
        plan.costTier, plan.joinCount, plan.planId,
    ))


def _ratio(hits, total):
    return {"hits": hits, "total": total, "rate": hits / total if total else 0.0}
