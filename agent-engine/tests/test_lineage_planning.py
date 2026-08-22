import json
from dataclasses import replace
from pathlib import Path

import pytest

from app.agents.query_planner import QueryPlannerAgent
from app.lineage.catalog import (
    canonical_bytes,
    canonical_hash,
    inspect_snapshot_integrity,
    load_mock_snapshot,
    refresh_snapshot_declarations,
    snapshot_hashes,
)
from app.lineage.planning import PlanEnumerator, PlanValidator, route_selection
from app.synthesis.sql_synthesizer import synthesize_plan


def _intent(metric="completion_rate", dimensions=None, filters=None, ordering=None,
            time_range=None, intent="aggregate"):
    return {
        "intent": intent,
        "metrics": [metric],
        "dimensions": dimensions or [],
        "filters": filters or [],
        "ordering": ordering,
        "time_range": time_range or {"type": "none", "granularity": None},
    }


def _compile(intent, snapshot, plan):
    candidates = PlanEnumerator().enumerate(intent, snapshot).candidates
    selected = next(item for item in candidates if item.planId == plan.planId)
    verdict = PlanValidator().validate(selected.planId, candidates, intent, snapshot)
    assert verdict["verdict"] == "PASS"
    return synthesize_plan(
        intent, snapshot, selected.to_dict(),
        validated_snapshot_fingerprint=verdict["snapshotFingerprint"],
    )


def test_canonical_fixture_and_snapshot_are_stable():
    root = Path(__file__).resolve().parents[2] / "src/main/resources"
    fixture = json.loads((root / "canonical_hash_fixture.json").read_text())
    expected = (root / "canonical_hash_fixture.sha256").read_text().strip()
    assert canonical_hash(fixture) == expected
    assert canonical_bytes(fixture).decode().startswith('{"array"')
    first = load_mock_snapshot()
    second = load_mock_snapshot()
    assert first == second
    assert len(first["catalogVersion"]) == 64
    integrity = inspect_snapshot_integrity(first)
    assert integrity.valid
    assert integrity.snapshot_fingerprint == snapshot_hashes(first)["fingerprint"]


@pytest.mark.parametrize("component", ["lineage", "metric", "schema"])
def test_integrity_rejects_stale_declarations_for_each_component(component):
    snapshot = load_mock_snapshot()
    if component == "lineage":
        snapshot["lineage"]["tables"][0]["tableType"] = "MUTATED"
    elif component == "metric":
        snapshot["metricDefinitions"][0]["formula"] = "COUNT(*)"
    else:
        table = min(snapshot["schemaProjection"])
        snapshot["schemaProjection"][table].append("tampered")
    result = inspect_snapshot_integrity(snapshot)
    assert not result.valid
    assert component in result.mismatched_components
    assert "catalog" in result.mismatched_components


@pytest.mark.parametrize("value", [None, "changed", "A" * 64])
def test_integrity_rejects_missing_or_invalid_declaration(value):
    snapshot = load_mock_snapshot()
    if value is None:
        snapshot.pop("lineageHash")
    else:
        snapshot["lineageHash"] = value
    result = inspect_snapshot_integrity(snapshot)
    assert not result.valid
    assert "lineage" in result.mismatched_components


def test_integrity_rejects_non_canonical_number():
    snapshot = load_mock_snapshot()
    snapshot["lineage"]["metricPaths"][0]["costTier"] = 1.5
    result = inspect_snapshot_integrity(snapshot)
    assert not result.valid
    assert result.reason


def test_enumerator_covers_direct_two_hop_filter_order_and_time_routes():
    snapshot = load_mock_snapshot()
    enum = PlanEnumerator()
    creator = enum.enumerate(_intent(dimensions=["creator"]), snapshot)
    assert any(route.edgeIds == ("play_content", "content_creator")
               for plan in creator.candidates for route in plan.fieldRoutes)

    filtered = enum.enumerate(_intent(filters=[{"field": "category", "op": "=", "value": "美食"}]), snapshot)
    assert any(route.semanticField == "category" and route.usages == ("FILTER",)
               and route.edgeIds == ("play_content",)
               for plan in filtered.candidates for route in plan.fieldRoutes)

    likes = enum.enumerate(_intent(
        metric="total_likes", dimensions=["category"],
        ordering={"field": "total_likes", "direction": "desc", "limit": 10},
        time_range={"type": "absolute", "absolute": {"start": "2023-10-01", "end": "2023-10-07"}, "granularity": "day"},
        intent="trend",
    ), snapshot)
    usages = {(route.semanticField, usage) for plan in likes.candidates
              for route in plan.fieldRoutes for usage in route.usages}
    assert {("total_likes", "ORDERING"), ("date", "TIME_FILTER"),
            ("date", "TIME_BUCKET")} <= usages
    assert len({plan.planId for plan in likes.candidates}) == len(likes.candidates)
    assert [p.planId for p in likes.candidates] == [
        p.planId for p in enum.enumerate(_intent(
            metric="total_likes", dimensions=["category"],
            ordering={"field": "total_likes", "direction": "desc", "limit": 10},
            time_range={"type": "absolute", "absolute": {"start": "2023-10-01", "end": "2023-10-07"}, "granularity": "day"}, intent="trend"), snapshot).candidates
    ]


def test_reverse_edge_and_non_mvp_are_rejected():
    snapshot = load_mock_snapshot()
    mutated = json.loads(json.dumps(snapshot))
    mutated["lineage"]["metricPaths"].append({
        "pathId": "reverse_only", "metricCode": "completion_rate",
        "sourceTable": "content_dim", "expressionRef": "primary", "eventFilterRef": None,
        "timeFieldRef": "content_id", "nativeDimensions": [],
        "supportedIntents": ["aggregate"], "freshness": "T1", "costTier": 1,
    })
    mutated["lineage"]["dimensionBindings"].append({
        "bindingId": "pd_reverse", "dimensionCode": "reverse_test", "tableName": "play_detail",
        "keyColumn": "content_id", "labelColumn": "content_id",
    })
    refresh_snapshot_declarations(mutated)
    result = PlanEnumerator().enumerate(_intent(dimensions=["reverse_test"]), mutated)
    assert any(item.code == "REVERSE_JOIN_NOT_ALLOWED" for item in result.rejected)
    assert not PlanEnumerator().enumerate({**_intent(), "metrics": ["completion_rate", "total_likes"]}, snapshot).candidates
    assert not PlanEnumerator().enumerate(_intent(intent="detail"), snapshot).candidates


def test_validator_rejects_missing_route_and_catalog_drift():
    snapshot = load_mock_snapshot()
    intent = _intent(filters=[{"field": "category", "op": "=", "value": "美食"}])
    plans = PlanEnumerator().enumerate(intent, snapshot).candidates
    assert PlanValidator().validate(plans[0].planId, plans, intent, snapshot)["verdict"] == "PASS"
    broken = replace(plans[0], fieldRoutes=())
    assert PlanValidator().validate(broken.planId, [broken], intent, snapshot)["code"] == "CANDIDATE_TAMPERED"
    tampered_source = replace(plans[0], sourceTable="metric_daily")
    assert PlanValidator().validate(
        tampered_source.planId, [tampered_source], intent, snapshot,
    )["code"] == "CANDIDATE_TAMPERED"
    drifted = {**snapshot, "catalogVersion": "0" * 64}
    rejected = PlanValidator().validate(plans[0].planId, plans, intent, drifted)
    assert rejected["verdict"] == "REJECT"
    assert rejected["code"] == "SNAPSHOT_INTEGRITY_MISMATCH"


def test_plan_compiler_uses_filter_route_and_selected_path():
    snapshot = load_mock_snapshot()
    intent = _intent(filters=[{"field": "category", "op": "=", "value": "美食"}])
    plan = PlanEnumerator().enumerate(intent, snapshot).candidates[0]
    sql = _compile(intent, snapshot, plan)
    assert "FROM play_detail pd JOIN content_dim cd" in sql
    assert "WHERE cd.category = '美食'" in sql
    assert "pd.category" not in sql


def test_plan_compiler_covers_creator_revenue_and_daily_fact_tradeoff():
    snapshot = load_mock_snapshot()
    enum = PlanEnumerator()

    creator_intent = _intent(dimensions=["creator"])
    creator_plan = next(
        plan for plan in enum.enumerate(creator_intent, snapshot).candidates
        if any(route.bindingId == "creator_creator" for route in plan.fieldRoutes)
    )
    creator_sql = _compile(creator_intent, snapshot, creator_plan)
    assert "JOIN content_dim cd" in creator_sql and "JOIN creator_dim ctd" in creator_sql
    assert "ctd.name AS creator" in creator_sql

    revenue_intent = _intent(metric="video_revenue", dimensions=["category"])
    revenue_plan = enum.enumerate(revenue_intent, snapshot).candidates[0]
    assert "JOIN content_dim cd" in _compile(revenue_intent, snapshot, revenue_plan)

    likes_intent = _intent(metric="total_likes", dimensions=["category"])
    likes_plans = enum.enumerate(likes_intent, snapshot).candidates
    daily = next(plan for plan in likes_plans if plan.metricPathId == "total_likes_daily")
    fact = next(plan for plan in likes_plans if plan.metricPathId == "total_likes_fact")
    assert "FROM metric_daily md" in _compile(likes_intent, snapshot, daily)
    fact_sql = _compile(likes_intent, snapshot, fact)
    assert "FROM user_behavior_fact ubf JOIN content_dim cd" in fact_sql
    assert "event_type = 'like'" in fact_sql


def test_compiler_rejects_self_consistent_snapshot_not_validated_by_validator():
    snapshot_s0 = load_mock_snapshot()
    intent = _intent(filters=[{"field": "category", "op": "=", "value": "美食"}])
    plans = PlanEnumerator().enumerate(intent, snapshot_s0).candidates
    verdict = PlanValidator().validate(plans[0].planId, plans, intent, snapshot_s0)
    assert verdict["verdict"] == "PASS"

    snapshot_s1 = json.loads(json.dumps(snapshot_s0))
    snapshot_s1["metricDefinitions"][0]["formula"] = "COUNT(*)"
    refresh_snapshot_declarations(snapshot_s1)
    assert inspect_snapshot_integrity(snapshot_s1).valid
    with pytest.raises(Exception, match="SNAPSHOT_INTEGRITY_MISMATCH"):
        synthesize_plan(
            intent, snapshot_s1, plans[0].to_dict(),
            validated_snapshot_fingerprint=verdict["snapshotFingerprint"],
        )


def test_compiler_uses_sealed_copy_after_original_is_mutated(monkeypatch):
    from app.lineage import catalog

    snapshot = load_mock_snapshot()
    intent = _intent(filters=[{"field": "category", "op": "=", "value": "美食"}])
    plans = PlanEnumerator().enumerate(intent, snapshot).candidates
    plan = plans[0]
    verdict = PlanValidator().validate(plan.planId, plans, intent, snapshot)
    real_seal = catalog.seal_compilation_snapshot

    def seal_then_mutate(source, **kwargs):
        sealed = real_seal(source, **kwargs)
        source["metricDefinitions"][0]["formula"] = "COUNT(*)"
        refresh_snapshot_declarations(source)
        return sealed

    monkeypatch.setattr(catalog, "seal_compilation_snapshot", seal_then_mutate)
    sql = synthesize_plan(
        intent, snapshot, plan.to_dict(),
        validated_snapshot_fingerprint=verdict["snapshotFingerprint"],
    )
    assert "FROM play_detail pd" in sql


class _FakePlannerLLM:
    def enabled(self):
        return True

    async def complete_json(self, _system, _user):
        return {"selected_plan_id": "fake", "reason_code": "LOW_COST",
                "explanation": "x", "confidence": 1, "sql": "DROP TABLE x"}


@pytest.mark.asyncio
async def test_planner_rejects_forbidden_physical_output():
    with pytest.raises(ValueError, match="forbidden"):
        await QueryPlannerAgent(_FakePlannerLLM()).select("普通查询", {}, [{"planId": "p"}])


def test_selection_only_calls_planner_for_freshness_tradeoff():
    snapshot = load_mock_snapshot()
    plans = PlanEnumerator().enumerate(_intent(metric="total_likes", dimensions=["category"]), snapshot).candidates
    source, selected = route_selection(plans)
    assert source == "PLANNER_AGENT"
    assert selected is None
