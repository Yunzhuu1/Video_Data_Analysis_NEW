import pytest

from app.graph import nodes
from app.graph.graph_builder import (
    route_after_enumerate,
    route_after_plan_validate,
    route_after_synthesize,
)
from app.settings import settings


class _Platform:
    def __init__(self):
        self.guard_calls = 0

    async def lineage_snapshot(self):
        from app.lineage.catalog import load_mock_snapshot

        return load_mock_snapshot()

    async def metric_definition(self, code):
        from app.lineage.catalog import load_mock_snapshot

        snapshot = load_mock_snapshot()
        return next(item for item in snapshot["metricDefinitions"] if item["metricCode"] == code)

    async def validate_sql(self, **_kwargs):
        self.guard_calls += 1
        return {"verdict": "PASS", "riskLevel": "LOW"}


class _IntegrityMismatchPlatform(_Platform):
    async def lineage_snapshot(self):
        from app.lineage.catalog import load_mock_snapshot

        snapshot = load_mock_snapshot()
        snapshot["metricDefinitions"][0]["formula"] = "COUNT(*)"
        return snapshot


@pytest.mark.asyncio
async def test_planning_off_is_explicit_legacy_fallback(monkeypatch):
    monkeypatch.setattr(settings, "lineage_planning_mode", "off")
    state = {"semantic_ok": True, "resolved_intent": {}, "warnings": []}
    result = await nodes.plan_enumerate_node(state, _Platform())
    assert result["plan_selection_source"] == "OFF"
    assert result["legacy_planner_fallback"] is True
    assert "candidate_plans" not in result


@pytest.mark.asyncio
async def test_active_enumerate_auto_validate(monkeypatch):
    monkeypatch.setattr(settings, "lineage_planning_mode", "active")
    state = {
        "semantic_ok": True, "question": "各分类视频收益", "warnings": [],
        "resolved_intent": {"intent": "aggregate", "metrics": ["video_revenue"],
                            "dimensions": ["category"], "filters": [],
                            "time_range": {"type": "none", "granularity": None},
                            "ordering": None},
    }
    await nodes.plan_enumerate_node(state, _Platform())
    assert state["plan_selection_source"] == "AUTO_SINGLE"
    await nodes.plan_validate_node(state)
    assert state["plan_validation"]["verdict"] == "PASS"
    assert state["validated_snapshot_fingerprint"] == state["plan_validation"]["snapshotFingerprint"]
    assert state["lineage_edge_ids"] == ["revenue_content"]


@pytest.mark.asyncio
async def test_shadow_mode_observes_plan_but_compiles_legacy_sql(monkeypatch):
    monkeypatch.setattr(settings, "lineage_planning_mode", "shadow")
    monkeypatch.setattr(nodes, "synthesize", lambda intent, metric_defs: "SELECT legacy_path")

    def _unexpected_plan_compile(*args, **kwargs):
        raise AssertionError("shadow mode must not compile the selected lineage plan")

    monkeypatch.setattr(nodes, "synthesize_plan", _unexpected_plan_compile)
    state = {
        "semantic_ok": True,
        "question": "各分类视频收益",
        "warnings": [],
        "resolved_intent": {
            "intent": "aggregate",
            "metrics": ["video_revenue"],
            "dimensions": ["category"],
            "filters": [],
            "time_range": {"type": "none", "granularity": None},
            "ordering": None,
        },
    }

    await nodes.plan_enumerate_node(state, _Platform())
    await nodes.plan_validate_node(state)
    await nodes.sql_synthesize_node(state, _Platform())

    assert state["candidate_plans"]
    assert state["plan_validation"]["verdict"] == "PASS"
    assert state["sql_attempts"][-1]["sql"] == "SELECT legacy_path"
    assert state["sql_attempts"][-1]["assumptions"][-1] == "plan=legacy"


@pytest.mark.asyncio
async def test_synthesis_error_adds_audit_fields_without_changing_fallback_route(monkeypatch):
    from app.synthesis.sql_synthesizer import SynthesisError

    monkeypatch.setattr(settings, "lineage_planning_mode", "off")

    def unsupported(*args, **kwargs):
        raise SynthesisError("conflict multi-metric + metric-value filter not supported")

    monkeypatch.setattr(nodes, "synthesize", unsupported)
    state = {
        "semantic_ok": True, "resolved_intent": {
            "intent": "aggregate", "metrics": ["completion_rate", "engagement_rate"],
            "dimensions": ["category"], "filters": [],
            "time_range": {"type": "none"}, "ordering": None,
        },
    }
    await nodes.sql_synthesize_node(state, _Platform())
    assert state["semantic_ok"] is False
    assert state["synthesis_error_code"] == "SYNTHESIS_ERROR"
    assert state["synthesis_error_reason"] == (
        "conflict multi-metric + metric-value filter not supported"
    )
    assert "sql_attempts" not in state


@pytest.mark.asyncio
async def test_integrity_reject_routes_to_legacy_then_guard_without_retry(monkeypatch):
    monkeypatch.setattr(settings, "lineage_planning_mode", "active")
    monkeypatch.setattr(nodes, "synthesize", lambda _intent, _defs: "SELECT 1")

    def forbidden_plan_compile(*_args, **_kwargs):
        raise AssertionError("integrity-rejected snapshot must not reach plan compiler")

    monkeypatch.setattr(nodes, "synthesize_plan", forbidden_plan_compile)
    platform = _IntegrityMismatchPlatform()
    state = {
        "run_id": "integrity-run", "user_id": "eval", "question": "总播放量",
        "semantic_ok": True, "warnings": [], "planning_retry_count": 0,
        "resolved_intent": {
            "intent": "aggregate", "metrics": ["total_plays"], "dimensions": [],
            "filters": [], "time_range": {"type": "none"}, "ordering": None,
        },
    }

    await nodes.plan_enumerate_node(state, platform)
    assert route_after_enumerate(state) == "validate"
    assert state["plan_validation"]["verdict"] == "REJECT"
    assert state["plan_validation"]["code"] == "SNAPSHOT_INTEGRITY_MISMATCH"
    components = list(state["plan_validation"]["mismatchedComponents"])

    await nodes.plan_validate_node(state)
    assert route_after_plan_validate(state) == "synthesize"
    assert state["plan_validation"]["mismatchedComponents"] == components
    assert state["planning_retry_count"] == 0
    assert state["legacy_planner_fallback"] is True

    await nodes.sql_synthesize_node(state, platform)
    assert route_after_synthesize(state) == "guard"
    assert state["sql_attempts"][-1]["sql"] == "SELECT 1"
    await nodes.sql_hard_guard_node(state, platform)
    assert platform.guard_calls == 1
