import pytest
import pytest_asyncio

from app.graph import graph_builder, nodes
from app.graph.graph_builder import run_chatbi_graph
from app.memory.retriever import normalize_question
from app.memory.store import MemoryStore, compute_resolver_hash
from app.settings import settings


@pytest_asyncio.fixture(autouse=True)
async def fresh_graph():
    from langgraph.checkpoint.memory import InMemorySaver

    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False
    settings.memory_enabled = True
    graph_builder.init_graph(InMemorySaver())
    yield
    if nodes.memory is not None:
        await nodes.memory.close()
    nodes.memory = None
    settings.memory_enabled = False


async def _make_store():
    store = MemoryStore(":memory:")
    await store.init()
    nodes.memory = store
    return store


def _initial_state(question="最近7天播放量是多少"):
    return {
        "run_id": "run_memory",
        "user_id": "demo",
        "question": question,
        "graph_mode": "chatbi",
        "warnings": [],
        "errors": [],
    }


def _intent(**overrides):
    base = {
        "intent": "trend",
        "metrics": ["total_plays"],
        "dimensions": [],
        "time_range": {"type": "none", "granularity": None},
        "filters": [],
        "ordering": None,
        "confidence": 0.9,
        "coverage": "full",
    }
    base.update(overrides)
    return base


class _SpyResolver:
    """记录 resolve 调用（绑定方法语义正确）。"""

    def __init__(self, calls, intent_factory):
        self.calls = calls
        self.intent_factory = intent_factory

    async def resolve(self, **kwargs):
        self.calls["resolved"] += 1
        return self.intent_factory()


@pytest.mark.asyncio
async def test_memory_hit_reuses_intent_and_skips_llm(monkeypatch):
    store = await _make_store()
    await store.upsert(normalize_question("最近7天播放量是多少"),
                       _intent(), ["total_plays"], compute_resolver_hash())

    calls = {"resolved": 0}
    monkeypatch.setattr(nodes, "semantic_resolver", _SpyResolver(calls, _intent))

    state = await run_chatbi_graph(_initial_state())

    assert state["sql_source"] == "memory"
    assert state["memory_hit"] is True
    assert calls["resolved"] == 0  # LLM 未调用
    entry = await store.find_by_question(normalize_question("最近7天播放量是多少"))
    assert entry.hit_count == 2  # 命中后 record_hit 已更新


@pytest.mark.asyncio
async def test_metrics_mismatch_not_hit(monkeypatch):
    store = await _make_store()
    await store.upsert(normalize_question("最近7天播放量是多少"),
                       _intent(), ["total_plays"], compute_resolver_hash())

    calls = {"resolved": 0}
    monkeypatch.setattr(nodes, "semantic_resolver", _SpyResolver(calls, _intent))

    # 问"点赞量"→ metrics 不一致 → 不直通 → 走 LLM
    state = await run_chatbi_graph(_initial_state(question="最近7天点赞量是多少"))

    assert calls["resolved"] == 1
    assert state.get("sql_source") != "memory"


@pytest.mark.asyncio
async def test_acceptable_recheck_fail_degrades(monkeypatch):
    store = await _make_store()
    # 存储条目 confidence 0.1 → acceptable 复检不过 → 降级 miss（走 LLM）
    await store.upsert(normalize_question("最近7天播放量是多少"),
                       _intent(confidence=0.1), ["total_plays"], compute_resolver_hash())

    calls = {"resolved": 0}
    monkeypatch.setattr(nodes, "semantic_resolver", _SpyResolver(calls, _intent))

    state = await run_chatbi_graph(_initial_state())

    assert state.get("memory_band") == "hit_rejected"
    assert calls["resolved"] == 1
    assert state.get("sql_source") != "memory"


@pytest.mark.asyncio
async def test_catalog_invalid_not_hit(monkeypatch):
    store = await _make_store()
    # 存储条目引用不存在的指标码 → catalog 校验失败 → 不直通
    await store.upsert(normalize_question("最近7天播放量是多少"),
                       _intent(metrics=["nonexistent_metric"]), ["nonexistent_metric"],
                       compute_resolver_hash())

    calls = {"resolved": 0}
    monkeypatch.setattr(nodes, "semantic_resolver", _SpyResolver(calls, _intent))

    state = await run_chatbi_graph(_initial_state())

    assert calls["resolved"] == 1
    assert state.get("sql_source") != "memory"
