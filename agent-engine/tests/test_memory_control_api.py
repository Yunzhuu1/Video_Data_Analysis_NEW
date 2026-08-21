import pytest
from fastapi import HTTPException

from app.api import routes
from app.api.routes import MemoryClearRequest, MemorySeedRequest
from app.graph import nodes
from app.memory.retriever import normalize_question
from app.memory.store import MemoryStore, compute_resolver_hash
from app.settings import settings


async def _make_store():
    store = MemoryStore(":memory:")
    await store.init()
    nodes.memory = store
    settings.memory_enabled = True
    return store


def _seed(namespace="eval-1"):
    return MemorySeedRequest(namespace=namespace, question="最近7天点赞量是多少",
                             intent={"intent": "trend", "metrics": ["total_plays"]},
                             metric_codes=["total_plays"])


@pytest.mark.asyncio
async def test_seed_rejects_default_namespace():
    store = await _make_store()
    try:
        with pytest.raises(HTTPException) as e:
            await routes.memory_seed(_seed(namespace="default"), settings.internal_api_token)
        assert e.value.status_code == 400
    finally:
        await store.close()
        nodes.memory = None


@pytest.mark.asyncio
async def test_seed_requires_token():
    store = await _make_store()
    try:
        with pytest.raises(HTTPException) as e:
            await routes.memory_seed(_seed(), None)
        assert e.value.status_code == 403
    finally:
        await store.close()
        nodes.memory = None


@pytest.mark.asyncio
async def test_seed_clear_entries_roundtrip():
    store = await _make_store()
    try:
        r = await routes.memory_seed(_seed(), settings.internal_api_token)
        assert r["namespace"] == "eval-1"
        entries = await routes.memory_entries("eval-1", settings.internal_api_token)
        assert entries["count"] == 1
        assert entries["entries"][0]["norm_question"] == normalize_question("最近7天点赞量是多少")
        d = await routes.memory_entries("default", settings.internal_api_token)
        assert d["count"] == 0  # default 不受污染
        await routes.memory_clear(MemoryClearRequest(namespace="eval-1"), settings.internal_api_token)
        await routes.memory_clear(MemoryClearRequest(namespace="eval-1"), settings.internal_api_token)  # 幂等
        assert (await routes.memory_entries("eval-1", settings.internal_api_token))["count"] == 0
    finally:
        await store.close()
        nodes.memory = None


@pytest.mark.asyncio
async def test_namespace_isolation_in_store():
    store = await _make_store()
    try:
        h = compute_resolver_hash()
        await store.upsert(normalize_question("问题X"), {"intent": "trend"}, ["total_plays"], h, namespace="eval-1")
        await store.upsert(normalize_question("问题X"), {"intent": "aggregate"}, ["total_plays"], h, namespace="default")
        e1 = await store.find_by_question(normalize_question("问题X"), namespace="eval-1")
        d1 = await store.find_by_question(normalize_question("问题X"), namespace="default")
        assert e1.resolved_intent["intent"] == "trend"
        assert d1.resolved_intent["intent"] == "aggregate"
    finally:
        await store.close()
        nodes.memory = None
