"""LanceVectorStore 单测：schema/写入/检索/管理 + 中文 FTS 可用性（1.1/1.2）。"""
import numpy as np
import pytest

from app.memory.store import MemoryEntry
from app.memory.vector_store import DEFAULT_VECTOR_DIM, LanceVectorStore


class FakeProvider:
    """确定性 fake embedding：text -> 固定向量（同文本同向量）。"""

    def __init__(self, vectors=None, default=None, fail=False):
        self.vectors = vectors or {}
        self.default = default if default is not None else [0.0] * DEFAULT_VECTOR_DIM
        self.fail = fail

    async def embed(self, text):
        if self.fail:
            return None
        if text in self.vectors:
            return list(self.vectors[text])
        # 确定性伪随机：同文本同向量
        rng = np.random.default_rng(abs(hash(text)) % (2**32))
        return rng.random(DEFAULT_VECTOR_DIM).astype("float32").tolist()


def _vec(fill=0.0):
    return [float(fill)] * DEFAULT_VECTOR_DIM


@pytest.mark.asyncio
async def test_init_creates_empty_table(tmp_path):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider())
    await store.init()
    try:
        assert store._table is not None
        assert await store.all() == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_upsert_find_all_and_existing_bump(tmp_path):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider())
    await store.init()
    try:
        eid = await store.upsert("最近7天播放量是多少", {"intent": "trend"}, ["total_plays"], "h")
        assert eid >= 1
        got = await store.find_by_question("最近7天播放量是多少", "default")
        assert got is not None and got.metric_codes == ["total_plays"] and got.hit_count == 1
        # 同 (ns, norm) upsert → 更新 + hit_count+1
        eid2 = await store.upsert("最近7天播放量是多少", {"intent": "trend"}, ["total_plays"], "h")
        assert eid2 == eid
        assert (await store.find_by_question("最近7天播放量是多少")).hit_count == 2
        # namespace 隔离
        await store.upsert("统计各分类总播放量", {"intent": "aggregate"}, ["total_plays"], "h", namespace="eval-x")
        assert len(await store.all("default")) == 1
        assert len(await store.all("eval-x")) == 1
        assert len(await store.all()) == 2
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_embed_failure_skips_persist(tmp_path):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider(fail=True))
    await store.init()
    try:
        eid = await store.upsert("最近7天播放量是多少", {"intent": "trend"}, ["total_plays"], "h")
        assert eid == -1
        assert await store.all() == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_record_hit_clear_delete(tmp_path):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider())
    await store.init()
    try:
        eid = await store.upsert("最近7天播放量是多少", {"intent": "trend"}, ["total_plays"], "h")
        await store.record_hit(eid)
        assert (await store.find_by_question("最近7天播放量是多少")).hit_count == 2
        await store.delete(eid)
        assert await store.all() == []
        await store.upsert("统计各分类总播放量", {"intent": "aggregate"}, ["total_plays"], "h")
        await store.upsert("最近7天点赞量是多少", {"intent": "trend"}, ["total_likes"], "h")
        await store.clear("default")
        assert await store.all() == []
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_search_by_vector_returns_cosine_sorted(tmp_path):
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider())
    await store.init()
    try:
        v1 = _vec(1.0)  # 与 query 完全相同
        v2 = [1.0] * 1024 + [0.0] * 1024
        await store.upsert("问题甲", {"intent": "aggregate"}, ["total_plays"], "h")
        # 覆盖存储的 embedding：直接再插入一条已知向量
        store.provider.vectors["问题乙"] = v1
        store.provider.vectors["问题丙"] = v2
        await store.upsert("问题乙", {"intent": "aggregate"}, ["total_plays"], "h")
        await store.upsert("问题丙", {"intent": "aggregate"}, ["total_plays"], "h")
        hits = await store.search_by_vector(v1, "default", limit=5)
        assert hits and hits[0][0].norm_question == "问题乙"
        assert abs(hits[0][1] - 1.0) < 1e-4  # cos=1
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_fts_chinese_icu(tmp_path):
    """任务 1.2：中文 FTS（ICU 分词）可用——'播放量' 应命中相关条目，'点赞量' 命中点赞条目。"""
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=FakeProvider())
    await store.init()
    try:
        await store.upsert("最近7天播放量是多少", {"intent": "trend"}, ["total_plays"], "h")
        await store.upsert("统计各分类总播放量", {"intent": "aggregate"}, ["total_plays"], "h")
        await store.upsert("最近7天点赞量是多少", {"intent": "trend"}, ["total_likes"], "h")
        hits = await store.fts_search("播放量", "default", limit=10)
        assert len(hits) >= 2
        names = [e.norm_question for e, _ in hits]
        # ICU 对中文按字切分 → 共享字符也命中（弱信号），但相关条目必须排前
        assert names[0] == "最近7天播放量是多少"
        assert names.index("最近7天点赞量是多少") > names.index("统计各分类总播放量") or "最近7天点赞量是多少" not in names[:2]
        likes = [e.norm_question for e, _ in await store.fts_search("点赞量", "default", limit=10)]
        assert likes[0] == "最近7天点赞量是多少"
    finally:
        await store.close()
