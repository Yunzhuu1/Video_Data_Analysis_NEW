import pytest

from app.memory.store import MemoryStore, compute_resolver_hash


@pytest.mark.asyncio
async def test_upsert_and_find(tmp_path):
    store = MemoryStore(str(tmp_path / "m.sqlite"))
    await store.init()
    try:
        h = compute_resolver_hash()
        eid = await store.upsert("最近7天播放量是多少", {"intent": "trend", "metrics": ["total_plays"]}, ["total_plays"], h)
        assert eid is not None
        entry = await store.find_by_question("最近7天播放量是多少")
        assert entry is not None
        assert entry.resolved_intent["metrics"] == ["total_plays"]
        assert entry.hit_count == 1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_upsert_same_question_increments_hit(tmp_path):
    store = MemoryStore(str(tmp_path / "m.sqlite"))
    await store.init()
    try:
        h = compute_resolver_hash()
        await store.upsert("问题A", {"intent": "aggregate", "metrics": ["total_plays"]}, ["total_plays"], h)
        eid2 = await store.upsert("问题A", {"intent": "aggregate", "metrics": ["total_plays"]}, ["total_plays"], h)
        entry = await store.find_by_question("问题A")
        assert entry.id == eid2
        assert entry.hit_count == 2
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_record_hit_and_delete(tmp_path):
    store = MemoryStore(str(tmp_path / "m.sqlite"))
    await store.init()
    try:
        h = compute_resolver_hash()
        eid = await store.upsert("问题B", {"intent": "trend"}, ["total_plays"], h)
        await store.record_hit(eid)
        entry = await store.find_by_question("问题B")
        assert entry.hit_count == 2
        await store.delete(eid)
        assert await store.find_by_question("问题B") is None
    finally:
        await store.close()
