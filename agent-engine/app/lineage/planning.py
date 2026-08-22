from __future__ import annotations

import hashlib
import itertools
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.lineage.catalog import (
    SnapshotIntegrityError,
    canonical_bytes,
    require_snapshot_integrity,
)

Usage = Literal["GROUP_BY", "FILTER", "ORDERING", "TIME_FILTER", "TIME_BUCKET"]


@dataclass(frozen=True)
class FieldRoute:
    semanticField: str
    usages: tuple[Usage, ...]
    routeKind: str
    bindingId: str | None = None
    metricPathId: str | None = None
    edgeIds: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateQueryPlan:
    planId: str
    metricPathId: str
    fieldRoutes: tuple[FieldRoute, ...]
    sourceTable: str
    freshness: str
    costTier: int
    joinCount: int
    catalogVersion: str
    snapshotFingerprint: str
    legalityEvidence: tuple[str, ...] = ("PASS",)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RejectedPlan:
    metricPathId: str | None
    code: str
    reason: str


@dataclass
class EnumerationResult:
    candidates: list[CandidateQueryPlan] = field(default_factory=list)
    rejected: list[RejectedPlan] = field(default_factory=list)


class PlanEnumerator:
    def __init__(self, max_hops: int = 2, max_candidates: int = 5):
        self.max_hops = max_hops
        self.max_candidates = max_candidates

    def enumerate(self, intent: dict[str, Any], snapshot: dict[str, Any]) -> EnumerationResult:
        integrity = require_snapshot_integrity(snapshot)
        fingerprint = integrity.snapshot_fingerprint
        if fingerprint is None:  # pragma: no cover - guaranteed by require
            raise SnapshotIntegrityError(integrity)
        metrics = intent.get("metrics") or []
        if len(metrics) != 1:
            return EnumerationResult(rejected=[RejectedPlan(None, "NON_MVP_MULTI_METRIC", "single metric only")])
        if intent.get("intent") not in {"aggregate", "trend", "ranking"}:
            return EnumerationResult(rejected=[RejectedPlan(None, "NON_MVP_INTENT", "unsupported intent")])
        lineage = snapshot["lineage"]
        paths = sorted(
            (p for p in lineage["metricPaths"] if p["metricCode"] == metrics[0]),
            key=lambda p: p["pathId"],
        )
        result = EnumerationResult()
        for path in paths:
            if intent["intent"] not in path["supportedIntents"]:
                result.rejected.append(RejectedPlan(path["pathId"], "UNSUPPORTED_INTENT", "path intent"))
                continue
            requirements = self._requirements(intent, metrics[0])
            options: list[list[FieldRoute]] = []
            failed = None
            for semantic_field, usages, kind in requirements:
                routes = self._routes(path, semantic_field, usages, kind, lineage)
                if not routes:
                    failed = semantic_field
                    break
                options.append(routes)
            if failed:
                bindings = [b for b in lineage["dimensionBindings"]
                            if b["dimensionCode"] == failed]
                reverse = any(
                    self._bfs(binding["tableName"], path["sourceTable"], lineage["joinEdges"])
                    is not None
                    for binding in bindings
                )
                code = "REVERSE_JOIN_NOT_ALLOWED" if reverse else "NO_FIELD_ROUTE"
                result.rejected.append(RejectedPlan(path["pathId"], code, failed))
                continue
            for combination in itertools.product(*options):
                routes = tuple(sorted(combination, key=lambda r: (r.semanticField, r.usages, r.bindingId or "")))
                edges = {edge for route in routes for edge in route.edgeIds}
                raw = {
                    "metricPathId": path["pathId"],
                    "fieldRoutes": [asdict(route) for route in routes],
                    "catalogVersion": snapshot["catalogVersion"],
                    "snapshotFingerprint": fingerprint,
                }
                plan_id = hashlib.sha256(canonical_bytes(raw)).hexdigest()[:16]
                result.candidates.append(CandidateQueryPlan(
                    plan_id, path["pathId"], routes, path["sourceTable"], path["freshness"],
                    int(path["costTier"]), len(edges), snapshot["catalogVersion"], fingerprint,
                ))
        unique = {plan.planId: plan for plan in result.candidates}
        result.candidates = sorted(unique.values(), key=lambda p: (p.costTier, p.joinCount, p.metricPathId, p.planId))[:self.max_candidates]
        return result

    @staticmethod
    def _requirements(intent: dict[str, Any], metric: str):
        merged: dict[tuple[str, str], set[Usage]] = {}
        for dim in intent.get("dimensions") or []:
            merged.setdefault((dim, "DIMENSION_BINDING"), set()).add("GROUP_BY")
        for flt in intent.get("filters") or []:
            field = str(flt.get("field") or "")
            kind = "METRIC_EXPRESSION" if field == metric else "DIMENSION_BINDING"
            merged.setdefault((field, kind), set()).add("FILTER")
        ordering = intent.get("ordering") or {}
        order_field = ordering.get("field") or ordering.get("metric")
        if order_field:
            kind = "METRIC_EXPRESSION" if order_field == metric else "DIMENSION_BINDING"
            merged.setdefault((str(order_field), kind), set()).add("ORDERING")
        time_range = intent.get("time_range") or {}
        if time_range.get("type") not in {None, "none"}:
            merged.setdefault(("date", "TIME_FIELD"), set()).add("TIME_FILTER")
        if time_range.get("granularity") or intent.get("intent") == "trend":
            merged.setdefault(("date", "TIME_FIELD"), set()).add("TIME_BUCKET")
        return [(field, tuple(sorted(usages)), kind) for (field, kind), usages in sorted(merged.items())]

    def _routes(self, path, field, usages, kind, lineage) -> list[FieldRoute]:
        if kind == "METRIC_EXPRESSION":
            return [FieldRoute(field, usages, kind, metricPathId=path["pathId"])]
        if kind == "TIME_FIELD":
            return [FieldRoute(field, usages, kind, metricPathId=path["pathId"])]
        bindings = [b for b in lineage["dimensionBindings"] if b["dimensionCode"] == field]
        found: list[FieldRoute] = []
        for binding in sorted(bindings, key=lambda b: b["bindingId"]):
            edge_ids = self._bfs(path["sourceTable"], binding["tableName"], lineage["joinEdges"])
            if edge_ids is not None:
                found.append(FieldRoute(field, usages, kind, bindingId=binding["bindingId"], edgeIds=tuple(edge_ids)))
        if any(not route.edgeIds for route in found):
            return [route for route in found if not route.edgeIds]
        return found

    def _bfs(self, source: str, target: str, edges: list[dict[str, Any]]) -> list[str] | None:
        if source == target:
            return []
        queue = deque([(source, [])])
        visited = {source}
        while queue:
            table, path = queue.popleft()
            if len(path) >= self.max_hops:
                continue
            outgoing = sorted((e for e in edges if e["fromTable"] == table), key=lambda e: e["edgeId"])
            for edge in outgoing:
                if edge["cardinalityFromTo"] not in {"N:1", "1:1"}:
                    continue
                next_table = edge["toTable"]
                next_path = path + [edge["edgeId"]]
                if next_table == target:
                    return next_path
                if next_table not in visited:
                    visited.add(next_table)
                    queue.append((next_table, next_path))
        return None


def route_selection(candidates: list[CandidateQueryPlan]) -> tuple[str, str | None]:
    if not candidates:
        return "LEGACY_FALLBACK", None
    if len(candidates) == 1:
        return "AUTO_SINGLE", candidates[0].planId
    freshness = {plan.freshness for plan in candidates}
    if len(freshness) == 1:
        selected = min(candidates, key=lambda p: (p.costTier, p.joinCount, p.planId))
        return "AUTO_POLICY", selected.planId
    return "PLANNER_AGENT", None


class PlanValidator:
    def __init__(self, max_hops: int = 2, max_candidates: int = 5):
        self.max_hops = max_hops
        self.max_candidates = max_candidates

    def validate(self, selected_plan_id: str | None, candidates: list[CandidateQueryPlan],
                 intent: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        try:
            integrity = require_snapshot_integrity(snapshot)
        except SnapshotIntegrityError as exc:
            return self._integrity_failure(exc)
        by_id = {plan.planId: plan for plan in candidates}
        if selected_plan_id not in by_id:
            return self._failure("INVALID_PLAN_ID", "selected plan is not a candidate")
        plan = by_id[selected_plan_id]
        if plan.snapshotFingerprint != integrity.snapshot_fingerprint:
            return self._failure(
                "SNAPSHOT_INTEGRITY_MISMATCH",
                "candidate snapshot fingerprint differs from current snapshot",
                verdict="REJECT",
                mismatchedComponents=["snapshotFingerprint"],
            )
        if plan.catalogVersion != snapshot.get("catalogVersion"):
            return self._failure("CATALOG_VERSION_MISMATCH", "plan snapshot changed")
        canonical = {
            item.planId: item
            for item in PlanEnumerator(self.max_hops, self.max_candidates).enumerate(
                intent, snapshot,
            ).candidates
        }
        if canonical.get(selected_plan_id) != plan:
            return self._failure(
                "CANDIDATE_TAMPERED",
                "selected candidate does not match the frozen snapshot enumeration",
            )
        expected = PlanEnumerator._requirements(intent, (intent.get("metrics") or [""])[0])
        actual = {(route.semanticField, route.routeKind): set(route.usages) for route in plan.fieldRoutes}
        for semantic_field, usages, kind in expected:
            if not set(usages) <= actual.get((semantic_field, kind), set()):
                return self._failure("MISSING_FIELD_ROUTE", f"missing {semantic_field}/{usages}")
        edge_map = {edge["edgeId"]: edge for edge in snapshot["lineage"]["joinEdges"]}
        for route in plan.fieldRoutes:
            current = plan.sourceTable
            for edge_id in route.edgeIds:
                edge = edge_map.get(edge_id)
                if not edge or edge["fromTable"] != current or edge["cardinalityFromTo"] not in {"N:1", "1:1"}:
                    return self._failure("INVALID_JOIN_DIRECTION", edge_id)
                current = edge["toTable"]
        return {"verdict": "PASS", "code": None, "reason": None, "suggestion": None,
                "snapshotFingerprint": integrity.snapshot_fingerprint,
                "mismatchedComponents": []}

    @staticmethod
    def _failure(code: str, reason: str, *, verdict: str = "REPLAN", **extra):
        return {"verdict": verdict, "code": code, "reason": reason,
                "suggestion": "select another enumerated plan" if verdict == "REPLAN" else None,
                **extra}

    @classmethod
    def _integrity_failure(cls, exc: SnapshotIntegrityError):
        result = exc.result
        return cls._failure(
            "SNAPSHOT_INTEGRITY_MISMATCH", str(exc), verdict="REJECT",
            mismatchedComponents=list(result.mismatched_components),
            snapshotFingerprint=result.snapshot_fingerprint,
        )
