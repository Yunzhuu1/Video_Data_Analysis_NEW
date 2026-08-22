from pathlib import Path

"""relative-time-synthesis：time_expand 集成 + nodes 展开单测。"""
import pytest

from app.graph import graph_builder, nodes
from app.graph.graph_builder import run_chatbi_graph
from app.settings import settings


# ------------------------------------------------------------------ 1.x 纯函数（已在 test_time_expand 覆盖，这里补集成）
@pytest.mark.asyncio
async def test_expand_relative_time_mock_anchor(monkeypatch):
    from app.graph.nodes import _expand_relative_time

    monkeypatch.setattr(settings, "platform_calls_enabled", False)
    relative = {"amount": 7, "unit": "day", "granularity": "day"}
    mdefs = {"total_plays": {"metricCode": "total_plays", "sourceTable": "metric_daily", "timeField": "date"}}
    intent = {"intent": "trend", "metrics": ["total_plays"], "dimensions": ["category"],
              "time_range": relative}
    state = {"run_id": "r", "user_id": "u", "question": "q"}
    expanded = await _expand_relative_time(relative, mdefs, intent, state, None)
    assert expanded["type"] == "absolute"
    assert expanded["absolute"]["start"] == "2023-10-25"
    assert expanded["absolute"]["end"] == "2023-10-31"


class _AnchorPlatform:
    def __init__(self, anchor="2023-10-31T23:59:59+08:00"):
        self.anchor = anchor
        self.sql = None

    async def execute_sql(self, **kwargs):
        self.sql = kwargs["sql"]
        return {"rows": [{"anchor_date": self.anchor}]}


@pytest.mark.asyncio
async def test_real_anchor_uses_legacy_resolved_fact_path(monkeypatch):
    from app.graph.nodes import _expand_relative_time

    monkeypatch.setattr(settings, "platform_calls_enabled", True)
    monkeypatch.setattr(settings, "lineage_planning_mode", "off")
    platform = _AnchorPlatform()
    relative = {"type": "relative", "relative": {"amount": 7, "unit": "day"}}
    mdefs = {"total_plays": {
        "metricCode": "total_plays", "sourceTable": "metric_daily", "timeField": "date",
        "formula": "total_plays", "factFormula": "COUNT(*)", "factEventFilter": "event_type='play'",
    }}
    intent = {"intent": "ranking", "metrics": ["total_plays"], "dimensions": ["content"]}

    expanded = await _expand_relative_time(relative, mdefs, intent,
                                            {"run_id": "r", "question": "q"}, platform)

    assert platform.sql == (
        "SELECT MAX(DATE(ubf.timestamp)) AS anchor_date FROM user_behavior_fact ubf"
    )
    assert expanded["absolute"] == {"start": "2023-10-25", "end": "2023-10-31"}


@pytest.mark.asyncio
async def test_real_anchor_uses_validated_plan_path(monkeypatch):
    from app.graph.nodes import _expand_relative_time

    monkeypatch.setattr(settings, "platform_calls_enabled", True)
    monkeypatch.setattr(settings, "lineage_planning_mode", "active")
    platform = _AnchorPlatform("2023-10-31 12:00:00")
    relative = {"type": "relative", "relative": {"amount": 1, "unit": "day"}}
    mdefs = {"video_revenue": {
        "metricCode": "video_revenue", "sourceTable": "video_revenue", "timeField": "stat_date",
    }}
    intent = {"intent": "trend", "metrics": ["video_revenue"], "dimensions": ["content"]}
    state = {
        "run_id": "r", "question": "q", "plan_validation": {"verdict": "PASS"},
        "selected_plan_id": "p1",
        "candidate_plans": [{"planId": "p1", "metricPathId": "video_revenue_daily"}],
        "lineage_snapshot": {"lineage": {"metricPaths": [{
            "pathId": "video_revenue_daily", "sourceTable": "video_revenue",
            "timeFieldRef": "stat_date",
        }]}}
    }

    expanded = await _expand_relative_time(relative, mdefs, intent, state, platform)

    assert platform.sql == "SELECT MAX(DATE(vr.stat_date)) AS anchor_date FROM video_revenue vr"
    assert expanded["absolute"] == {"start": "2023-10-31", "end": "2023-10-31"}


@pytest.mark.asyncio
async def test_invalid_anchor_raises_stable_error(monkeypatch):
    from app.graph.nodes import _expand_relative_time

    monkeypatch.setattr(settings, "platform_calls_enabled", True)
    monkeypatch.setattr(settings, "lineage_planning_mode", "off")
    platform = _AnchorPlatform("not-a-date")
    mdefs = {"total_plays": {
        "metricCode": "total_plays", "sourceTable": "metric_daily", "timeField": "date",
    }}
    with pytest.raises(ValueError, match="ANCHOR_DATE_INVALID"):
        await _expand_relative_time(
            {"amount": 7, "unit": "day"}, mdefs,
            {"intent": "trend", "metrics": ["total_plays"], "dimensions": []},
            {"run_id": "r", "question": "q"}, platform)


# ------------------------------------------------------------------ 2.x 集成：c03 合成 SQL 含时间过滤
class _FakeResolverRelative:
    """返回 relative time_range 的 intent（模拟 LLM 解析 c03）。"""

    async def resolve(self, question, catalog, dimensions, examples=None):
        return {
            "intent": "trend",
            "metrics": ["total_plays"],
            "dimensions": [],
            "time_range": {"type": "relative", "relative": {"amount": 7, "unit": "day"}, "granularity": "day"},
            "filters": [],
            "ordering": None,
            "confidence": 0.9,
            "coverage": "full",
        }


@pytest.fixture(autouse=True)
def fresh_graph():
    from langgraph.checkpoint.memory import InMemorySaver

    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False
    settings.memory_enabled = False
    graph_builder.init_graph(InMemorySaver())
    yield
    nodes.semantic_resolver = None


@pytest.mark.asyncio
async def test_relative_time_synthesizes_with_filter(monkeypatch):
    """c03「最近7天」：mock 锚点 2023-10-31 → 合成 SQL 含 WHERE date BETWEEN '2023-10-25' AND '2023-10-31'。"""
    monkeypatch.setattr(nodes, "semantic_resolver", _FakeResolverRelative())
    state = await run_chatbi_graph({
        "run_id": "rel_c03", "user_id": "eval", "question": "最近7天每天播放量是多少",
        "graph_mode": "chatbi", "warnings": [], "errors": []})
    sql = (state.get("sql_attempts") or [{}])[-1].get("sql", "")
    assert "BETWEEN '2023-10-25' AND '2023-10-31 23:59:59'" in sql
    assert state.get("sql_source") == "semantic"


# ------------------------------------------------------------------ 3.x R1 扩展（relative 子集断言）
def test_relative_c03_trend_pattern_assert():
    from app.eval.result_comparator import check_result

    rows = [
        {"date": "2023-10-25", "total_plays": 261},
        {"date": "2023-10-26", "total_plays": 287},  # up
        {"date": "2023-10-27", "total_plays": 271},
    ]
    exp = {"type": "trend_pattern", "points": [{"date": "2023-10-26", "direction": "up"}]}
    assert check_result(rows, exp, "trend").passed is True


def test_relative_n04_exact_assert():
    from app.eval.result_comparator import check_result

    assert check_result([{"v": 632}], {"type": "exact", "value": 632, "tolerance": 0.01}, "aggregate").passed is True
    assert check_result([{"v": 700}], {"type": "exact", "value": 632, "tolerance": 0.01}, "aggregate").passed is False


def test_cases_yaml_relative_expected_result_present():
    import json

    data = json.loads(Path("app/eval/cases.yaml").read_text())
    by_id = {c["id"]: c for c in data["cases"]}
    for cid in ("c03_last7d_daily_plays", "c13_lastweek_plays", "n04_multi_filter", "n09_ranked_time", "n10_ranked_time"):
        assert by_id[cid].get("expected_result"), f"{cid} missing expected_result"
        assert by_id[cid]["expected_result"].get("truth_source"), f"{cid} missing truth_source"
