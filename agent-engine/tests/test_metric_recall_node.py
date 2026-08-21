import json
from pathlib import Path

import pytest

from app.agents.semantic_resolver import SemanticResolver
from app.graph import nodes
from app.memory.retriever import MemoryHit
from app.memory.store import MemoryEntry, compute_resolver_hash
from app.settings import settings

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "src/main/resources/metric_catalog.json").read_text())


class _Platform:
    async def metric_catalog(self):
        return CATALOG


def _state(question="最近7天播放量是多少"):
    return {"question": question, "warnings": [], "memory_namespace": "default"}


def _intent():
    return {
        "intent": "aggregate", "metrics": ["total_plays"], "dimensions": [],
        "time_range": {"type": "none", "granularity": None}, "filters": [],
        "ordering": None, "confidence": 0.9, "coverage": "full",
    }


class _CaptureResolver:
    def __init__(self):
        self.calls = []

    async def resolve(self, **kwargs):
        self.calls.append(kwargs)
        return _intent()


@pytest.mark.asyncio
async def test_normal_topk_and_full_mode_catalogs(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", False)
    monkeypatch.setattr(settings, "metric_recall_top_k", 2)
    resolver = _CaptureResolver()
    monkeypatch.setattr(nodes, "semantic_resolver", resolver)

    monkeypatch.setattr(settings, "metric_recall_mode", "topk")
    topk_state = await nodes.semantic_resolve_node(_state(), _Platform())
    topk_codes = [x["metricCode"] for x in resolver.calls[-1]["catalog"]]
    assert "total_plays" in topk_codes
    assert len(topk_codes) == 2
    assert topk_state["metric_recall_mode"] == "topk"
    assert topk_state["metric_recall_prompt_catalog_count"] == 2

    monkeypatch.setattr(settings, "metric_recall_mode", "full")
    full_state = await nodes.semantic_resolve_node(_state(), _Platform())
    assert len(resolver.calls[-1]["catalog"]) == len(CATALOG)
    assert full_state["metric_recall_mode"] == "full"
    assert full_state["metric_recall_fallback"] is False


@pytest.mark.asyncio
async def test_user_prompt_built_once_measured_and_sent_as_same_string(monkeypatch):
    class _SpyLLM:
        user_prompt = None

        def enabled(self):
            return True

        async def complete_json(self, system_prompt, user_prompt):
            self.user_prompt = user_prompt
            return _intent()

    spy = _SpyLLM()
    monkeypatch.setattr(nodes, "semantic_resolver", SemanticResolver(spy))
    monkeypatch.setattr(settings, "memory_enabled", False)
    monkeypatch.setattr(settings, "metric_recall_mode", "topk")
    calls = 0
    original = nodes.build_semantic_user_prompt

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(nodes, "build_semantic_user_prompt", counted)
    state = await nodes.semantic_resolve_node(_state(), _Platform())
    assert calls == 1
    assert spy.user_prompt is not None
    assert state["semantic_prompt_chars"] == len(spy.user_prompt)


@pytest.mark.asyncio
async def test_memory_inject_uses_same_candidate_catalog(monkeypatch):
    entry = MemoryEntry("历史播放问法", _intent(), ["total_plays"], compute_resolver_hash())

    class _Retriever:
        async def search(self, *args, **kwargs):
            return [MemoryHit(entry, 0.88, "inject")]

    resolver = _CaptureResolver()
    monkeypatch.setattr(nodes, "memory", object())
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(settings, "metric_recall_mode", "topk")
    monkeypatch.setattr(settings, "metric_recall_top_k", 2)
    monkeypatch.setattr(nodes, "build_retriever", lambda *args: _Retriever())
    monkeypatch.setattr(nodes, "semantic_resolver", resolver)
    state = await nodes.semantic_resolve_node(_state(), _Platform())
    call = resolver.calls[0]
    assert len(call["catalog"]) == state["metric_recall_prompt_catalog_count"] == 2
    assert call["examples"] == [("历史播放问法", _intent())]
    assert state["semantic_prompt_chars"] is not None


@pytest.mark.asyncio
async def test_memory_hit_validates_with_full_catalog_and_skips_prompt(monkeypatch):
    entry = MemoryEntry("最近7天播放量是多少", _intent(), ["total_plays"], compute_resolver_hash())

    class _Retriever:
        async def search(self, *args, **kwargs):
            return [MemoryHit(entry, 1.0, "hit")]

    seen = {}

    def capture_hit(question, stored, catalog, aliases):
        seen["catalog"] = catalog
        return True

    resolver = _CaptureResolver()
    monkeypatch.setattr(nodes, "memory", object())
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(settings, "metric_recall_mode", "topk")
    monkeypatch.setattr(nodes, "build_retriever", lambda *args: _Retriever())
    monkeypatch.setattr(nodes, "hit_allowed", capture_hit)
    monkeypatch.setattr(nodes, "semantic_resolver", resolver)
    state = await nodes.semantic_resolve_node(_state(), _Platform())
    assert len(seen["catalog"]) == len(CATALOG)
    assert resolver.calls == []
    assert state["semantic_prompt_chars"] is None
    assert state["sql_source"] == "memory"
