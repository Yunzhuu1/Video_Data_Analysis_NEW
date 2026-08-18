"""HybridRetriever 单测（1.3，路径 B）：精确快路径 / 融合打分 / 降级 difflib / 三档边界。"""
import hashlib
import numpy as np
import pytest

from app.memory.retriever import HybridRetriever
from app.memory.vector_store import DEFAULT_VECTOR_DIM, LanceVectorStore
from tests.test_vector_store import FakeProvider


class CharBagProvider:
    """语义假 provider：字符袋向量（同字共享 → 相似文本高 cosine），模拟真实 embedding 行为。"""

    def available(self):
        return True

    async def embed(self, text):
        vec = np.zeros(DEFAULT_VECTOR_DIM, dtype="float32")
        for ch in text:
            idx = int(hashlib.md5(ch.encode()).hexdigest(), 16) % DEFAULT_VECTOR_DIM
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return (vec / norm if norm else vec).tolist()


async def _store(tmp_path, **entries):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=CharBagProvider())
    await store.init()
    for q, intent in entries.items():
        await store.upsert(q, intent, list(intent.get("metrics") or []), "h")
    return store


@pytest.mark.asyncio
async def test_exact_match_fast_path(tmp_path):
    store = await _store(tmp_path, **{"最近7天播放量是多少": {"intent": "trend", "metrics": ["total_plays"]}})
    r = HybridRetriever(store, CharBagProvider(), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        hits = await r.search("最近7天播放量是多少")
        assert hits and hits[0].band == "hit" and hits[0].score == 1.0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_fallback_difflib_when_embedding_unavailable(tmp_path):
    """embedding 不可用 → 降级 difflib（近重复 → hit/inject，行为同现状）。"""
    store = await _store(tmp_path, **{"最近7天播放量是多少": {"intent": "trend", "metrics": ["total_plays"]}})
    r = HybridRetriever(store, FakeProvider(fail=True), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        hits = await r.search("最近7天播放量是多少啊")
        assert hits and hits[0].band in ("hit", "inject")
        assert await r.search("统计各分类总分享量") == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_fused_path_near_repeat_hits(tmp_path):
    """路径 B 融合：近重复（字面近 + 语义近）→ hit。"""
    store = await _store(tmp_path, **{"最近7天播放量是多少": {"intent": "trend", "metrics": ["total_plays"]}})
    r = HybridRetriever(store, CharBagProvider(), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        hits = await r.search("最近7天播放量是多少啊")
        assert hits and hits[0].band == "hit"
        assert 0.0 < hits[0].score <= 1.0
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_inject_band_populated(tmp_path):
    """语义改写（共享大部分词）→ 落 inject 带。"""
    store = await _store(tmp_path, **{"统计各分类总播放量": {"intent": "aggregate", "metrics": ["total_plays"]}})
    r = HybridRetriever(store, CharBagProvider(), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        hits = await r.search("统计各分类的总播放量")  # 近义微调（加"的"）→ 注入带
        assert hits and hits[0].band in ("hit", "inject")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_unrelated_miss(tmp_path):
    store = await _store(tmp_path, **{"最近7天播放量是多少": {"intent": "trend", "metrics": ["total_plays"]}})
    r = HybridRetriever(store, CharBagProvider(), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        assert await r.search("统计各分类总分享量") == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_top1_band_sorted(tmp_path):
    """runner band 分层消费的语义：search 返回分数降序，top-1 即 best band。"""
    store = await _store(tmp_path, **{
        "最近7天播放量是多少": {"intent": "trend", "metrics": ["total_plays"]},
        "统计各分类总播放量": {"intent": "aggregate", "metrics": ["total_plays"]},
    })
    r = HybridRetriever(store, CharBagProvider(), hit_threshold=0.95, inject_threshold=0.85, weight=0.7)
    try:
        hits = await r.search("最近7天播放量是多少啊", limit=3)
        scores = [h.score for h in hits]
        assert scores == sorted(scores, reverse=True)
    finally:
        await store.close()
