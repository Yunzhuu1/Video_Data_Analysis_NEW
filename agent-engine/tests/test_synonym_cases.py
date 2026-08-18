import json
from pathlib import Path

import pytest

from app.eval.runner import DEFAULT_CASES
from app.memory.retriever import TextSimilarityRetriever, normalize_question
from app.memory.store import MemoryStore


def test_synonym_cases_load_and_golden_covered():
    data = json.loads(Path("app/eval/synonym_cases.yaml").read_text(encoding="utf-8"))
    syns = data["cases"]
    assert len(syns) == 20  # 5 类变换 × 4
    golden_cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))["cases"]
    golden_ids = {c["id"] for c in golden_cases if c.get("golden_spec")}
    for s in syns:
        assert s.get("golden_spec"), f"{s['id']} missing golden"
        assert s.get("source_case") in golden_ids, f"{s['id']} bad source_case"
        src_q = next(c["question"] for c in golden_cases if c["id"] == s["source_case"])
        assert s["question"] != src_q  # 同义重写，不得与 golden 相同


@pytest.mark.asyncio
async def test_band_layering_consistent_with_retriever():
    """band 分层与检索器输出一致（不绑定具体 band 值，向量化后不红）。"""
    store = MemoryStore(":memory:")
    await store.init()
    try:
        await store.upsert(normalize_question("最近7天播放量是多少"),
                           {"intent": "trend"}, ["total_plays"], "h", namespace="default")
        r = TextSimilarityRetriever(store, hit_threshold=0.95, inject_threshold=0.85)
        # 完全相同 → hit；语义不同（字符差大）→ miss；微异 → inject 或 hit
        hits = await r.search("最近7天播放量是多少")
        assert hits and hits[0].band == "hit"
        miss = await r.search("统计各分类总分享量")
        assert not miss
        # 微异同义 → 至少不是 miss（inject 或 hit）
        near = await r.search("最近7天播放数据是多少")
        assert not near or near[0].band in ("hit", "inject")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_runner_band_consistent_with_runtime_hit(monkeypatch, tmp_path):
    """3.1 一致性（eval-metrics review P1）：seed 指标不一致的相似条目（毒化）→
    runner band ≠ 'hit'（运行时 metrics_consistent 拦截 → hit_rejected），零偏差承诺。"""
    from app.eval import runner
    from app.graph import nodes
    from app.memory.embeddings import reset_embedding_provider
    from app.memory.retriever import normalize_question
    from app.memory.vector_store import LanceVectorStore
    from app.settings import settings
    from tests.test_hybrid_retriever import CharBagProvider

    monkeypatch.setattr(settings, "memory_store_backend", "lance")
    reset_embedding_provider(CharBagProvider())
    store = LanceVectorStore(str(tmp_path / "m.lance"), provider=CharBagProvider())
    await store.init()
    try:
        # 毒化条目：问题文本"点赞量"但 intent/metrics 是播放量（与 c25 同构）
        await store.upsert(normalize_question("最近7天点赞量是多少"),
                           {"intent": "trend", "metrics": ["total_plays"], "confidence": 0.9}, ["total_plays"], "h")
        nodes.memory = store

        bands = await runner._compute_synonym_bands(["最近7天点赞量是多少"], "default")
        # 精确快路径给 hit，但运行时四重判定（metrics 不一致）拦截 → hit_rejected ≠ hit
        assert bands["最近7天点赞量是多少"] == "hit_rejected"

        # 对照：指标一致条目 → 正常 hit
        await store.upsert(normalize_question("最近7天播放量是多少"),
                           {"intent": "trend", "metrics": ["total_plays"], "confidence": 0.9}, ["total_plays"], "h")
        bands2 = await runner._compute_synonym_bands(["最近7天播放量是多少"], "default")
        assert bands2["最近7天播放量是多少"] == "hit"
    finally:
        await store.close()
        nodes.memory = None
        reset_embedding_provider(None)
