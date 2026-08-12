import pytest

from app.graph import graph_builder, nodes
from app.graph.graph_builder import run_chatbi_graph
from app.settings import settings


class FakeResolver:
    def __init__(self, intent):
        self._intent = intent

    async def resolve(self, question, catalog, dimensions):
        return self._intent


@pytest.fixture(autouse=True)
def fresh_graph():
    from langgraph.checkpoint.memory import InMemorySaver

    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False
    graph_builder.init_graph(InMemorySaver())
    yield


def _initial_state(run_id="run_semantic"):
    return {
        "run_id": run_id,
        "user_id": "demo",
        "question": "analyze category play trends",
        "graph_mode": "chatbi",
        "warnings": [],
        "errors": [],
    }


@pytest.mark.asyncio
async def test_semantic_path_synthesizes_and_executes(monkeypatch):
    monkeypatch.setattr(
        nodes,
        "semantic_resolver",
        FakeResolver(
            {
                "intent": "trend",
                "metrics": ["total_plays"],
                "dimensions": ["category"],
                "time_range": {"type": "none", "granularity": "day"},
                "filters": [],
                "ordering": None,
                "confidence": 0.9,
                "coverage": "full",
            }
        ),
    )

    state = await run_chatbi_graph(_initial_state())

    assert state["sql_source"] == "semantic"
    last = state["sql_attempts"][-1]
    assert last["source"] == "semantic"
    assert "FROM md" in last["sql"]
    assert state["query_result"]["success"] is True
    assert state["validation_feedback"] == "PASS"


@pytest.mark.asyncio
async def test_resolve_failure_falls_back_to_raw_generation(monkeypatch):
    monkeypatch.setattr(nodes, "semantic_resolver", FakeResolver(None))

    state = await run_chatbi_graph(_initial_state())

    assert state["semantic_ok"] is False
    assert state["sql_source"] == "fallback"
    assert state["sql_attempts"][-1]["source"] == "fallback"
    assert state["query_result"]["success"] is True


@pytest.mark.asyncio
async def test_low_confidence_resolve_falls_back(monkeypatch):
    monkeypatch.setattr(
        nodes,
        "semantic_resolver",
        FakeResolver(
            {
                "intent": "aggregate",
                "metrics": [],
                "dimensions": [],
                "time_range": {"type": "none", "granularity": None},
                "filters": [],
                "ordering": None,
                "confidence": 0.2,
                "coverage": "partial",
            }
        ),
    )

    state = await run_chatbi_graph(_initial_state())

    assert state["semantic_ok"] is False
    assert state["sql_source"] == "fallback"


@pytest.mark.asyncio
async def test_synthesis_failure_falls_back(monkeypatch):
    # multi-metric intent cannot be synthesized in v1 -> degrade to raw SQL
    monkeypatch.setattr(
        nodes,
        "semantic_resolver",
        FakeResolver(
            {
                "intent": "aggregate",
                "metrics": ["total_plays", "total_likes"],
                "dimensions": [],
                "time_range": {"type": "none", "granularity": None},
                "filters": [],
                "ordering": None,
                "confidence": 0.9,
                "coverage": "full",
            }
        ),
    )

    state = await run_chatbi_graph(_initial_state())

    assert state["semantic_ok"] is False
    assert state["sql_source"] == "fallback"
    assert state["sql_attempts"][-1]["source"] == "fallback"


@pytest.mark.asyncio
async def test_replay_cassette_drives_semantic_path(monkeypatch, tmp_path):
    """replay 模式：手写 cassette 让语义解析命中，跑通 SEMANTIC_RESOLVE -> SQL_SYNTHESIZE。"""
    from app.clients.llm_client import settings as llm_settings
    from app.eval.fakellm import CassetteStore, request_key
    from app.prompts.semantic import SEMANTIC_SYSTEM_PROMPT, build_semantic_user_prompt
    from app.synthesis.sql_synthesizer import DIMENSIONS

    # deterministic prompt for this question + mock catalog
    catalog = [
        {"metricCode": "total_plays", "metricName": "播放量", "businessDefinition": "播放事件总数",
         "sourceTable": "metric_daily", "timeField": "date", "dimensions": ["date", "category"]},
        {"metricCode": "total_likes", "metricName": "点赞量", "businessDefinition": "点赞事件总数",
         "sourceTable": "metric_daily", "timeField": "date", "dimensions": ["date", "category"]},
        {"metricCode": "completion_rate", "metricName": "完播率", "businessDefinition": "完播率均值",
         "sourceTable": "play_detail", "timeField": "created_at", "dimensions": ["content"]},
    ]
    user_prompt = build_semantic_user_prompt("analyze category play trends", catalog, DIMENSIONS)
    key = request_key(SEMANTIC_SYSTEM_PROMPT, user_prompt)

    path = tmp_path / "cassette.json"
    store = CassetteStore(path)
    store.put(key, {
        "intent": "trend",
        "metrics": ["total_plays"],
        "dimensions": ["category"],
        "time_range": {"type": "none", "granularity": "day"},
        "filters": [],
        "ordering": None,
        "confidence": 0.95,
        "coverage": "full",
    })
    store.save()

    llm_settings.eval_llm_mode = "replay"
    llm_settings.eval_llm_cassette = str(path)
    monkeypatch.setattr(
        nodes,
        "semantic_resolver",
        __import__("app.agents.semantic_resolver", fromlist=["SemanticResolver"]).SemanticResolver(),
    )

    state = await run_chatbi_graph(_initial_state())

    assert state["sql_source"] == "semantic"
    assert "FROM md" in state["sql_attempts"][-1]["sql"]
    assert state["resolved_intent"]["metrics"] == ["total_plays"]
