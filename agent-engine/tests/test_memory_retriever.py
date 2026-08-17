import pytest

from app.memory.retriever import (
    TextSimilarityRetriever,
    extract_metric_names,
    metrics_consistent,
    normalize_question,
)
from app.memory.store import MemoryEntry

CATALOG = [
    {"metricCode": "total_plays", "metricName": "播放量"},
    {"metricCode": "total_likes", "metricName": "点赞量"},
]


def _entry(question: str, metric_codes: list[str]) -> MemoryEntry:
    return MemoryEntry(
        norm_question=normalize_question(question),
        resolved_intent={"intent": "aggregate", "metrics": metric_codes},
        metric_codes=metric_codes,
        resolver_hash="h",
    )


def test_normalize_question():
    assert normalize_question("  最近7天 播放量 是多少 ？ ") == "最近7天播放量是多少"
    assert normalize_question("最近7天") != normalize_question("最近30天")


@pytest.mark.asyncio
async def test_dual_threshold_bands(tmp_path):
    from app.memory.store import MemoryStore
    store = MemoryStore(str(tmp_path / "m.sqlite"))
    await store.init()
    try:
        await store.upsert(normalize_question("最近7天播放量是多少"),
                           {"intent": "trend"}, ["total_plays"], "h")
        r = TextSimilarityRetriever(store, hit_threshold=0.95, inject_threshold=0.85)
        # 完全相同 → hit
        hits = await r.search("最近7天播放量是多少")
        assert hits and hits[0].band == "hit"
        # 微异 → inject（"最近7天播放量是多少啊" 相似度高但 <1）
        inj = await r.search("最近7天播放量是多少啊")
        assert inj and inj[0].band in ("inject", "hit")
        # 完全不同 → miss
        miss = await r.search("统计各分类总分享量")
        assert not miss
    finally:
        await store.close()


def test_extract_metric_names():
    assert extract_metric_names("最近7天播放量", CATALOG) == ["total_plays"]
    assert extract_metric_names("最近7天点赞量", CATALOG) == ["total_likes"]
    assert extract_metric_names("分析播放情况", CATALOG) == []


def test_metrics_consistency_blocks_mismatch():
    # 库里是播放量，问点赞量 → 不一致 → 不直通
    entry = _entry("最近7天播放量是多少", ["total_plays"])
    assert metrics_consistent("最近7天点赞量是多少", entry, CATALOG) is False


def test_metrics_consistency_passes_match():
    entry = _entry("最近7天播放量是多少", ["total_plays"])
    assert metrics_consistent("最近7天播放量是多少", entry, CATALOG) is True


def test_metrics_consistency_unresolvable_blocks():
    # 匹配不到指标名 → 不直通（P2-3 收紧）
    entry = _entry("分析播放情况", ["total_plays"])
    assert metrics_consistent("分析播放情况", entry, CATALOG) is False
