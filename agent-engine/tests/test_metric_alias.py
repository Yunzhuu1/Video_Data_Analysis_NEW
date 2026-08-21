import pytest

"""metric-alias：指标表达别名（aliases.yaml + 最长匹配 + metrics_consistent 扩展）单测。"""
import json
from pathlib import Path

from app.memory.aliases import get_alias_bundle, get_aliases, load_alias_bundle, reset_aliases
from app.memory.retriever import (
    extract_metric_names,
    hit_allowed,
    metrics_consistent,
    normalize_question,
)
from app.memory.store import MemoryEntry

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text())


def _entry(question: str, metric_codes: list[str]) -> MemoryEntry:
    return MemoryEntry(
        norm_question=normalize_question(question),
        resolved_intent={"intent": "aggregate", "metrics": metric_codes, "confidence": 0.9},
        metric_codes=metric_codes,
        resolver_hash="h",
    )


def _aliases() -> dict[str, str]:
    reset_aliases()
    return get_aliases()


# ------------------------------------------------------------------ 数据校验
def test_aliases_yaml_valid_and_covered():
    bundle = get_alias_bundle()
    a = bundle.alias_records
    codes = {m["metricCode"] for m in CATALOG}
    names = {m["metricName"] for m in CATALOG}
    assert len(a) == 25
    assert all(x.metric_code in codes for x in a)
    assert all(x.alias not in names for x in a)          # 不覆盖 catalog 精确名
    assert len({x.alias for x in a}) == len(a)           # 无重复别名
    cases = json.loads(Path("app/eval/cases.yaml").read_text())["cases"]
    syn = json.loads(Path("app/eval/synonym_cases.yaml").read_text())["cases"]
    ids = {c["id"] for c in cases} | {s["id"] for s in syn}
    for x in a:
        assert all(cid in ids for cid in x.covered_by), f"{x.alias} bad covered_by"


def test_alias_bundle_map_and_records_are_same_source():
    bundle = get_alias_bundle()
    expected = {
        r.alias: r.metric_code
        for r in sorted(bundle.alias_records, key=lambda x: (-len(x.alias), x.alias, x.metric_code))
    }
    assert bundle.alias_map == get_aliases() == expected
    lengths = [len(x) for x in bundle.alias_map]
    assert lengths == sorted(lengths, reverse=True)


def test_alias_bundle_rejects_conflicting_duplicate(tmp_path):
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"aliases": [
        {"alias": "热度", "metric_code": "total_plays", "covered_by": []},
        {"alias": "热度", "metric_code": "total_likes", "covered_by": []},
    ]}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting alias"):
        load_alias_bundle(path)


# ------------------------------------------------------------------ 别名匹配
def test_extract_alias_match_and_default_none():
    al = _aliases()
    assert extract_metric_names("对比美食和游戏分类的播放趋势", CATALOG) == []
    assert extract_metric_names("对比美食和游戏分类的播放趋势", CATALOG, al) == ["total_plays"]
    assert extract_metric_names("游戏区完播表现怎么样", CATALOG, al) == ["completion_rate"]
    assert extract_metric_names("近7天互动最火热的分类", CATALOG, al) == ["engagement_rate"]


def test_extract_catalog_precedence_coexists():
    al = _aliases()
    # catalog 精确名与别名共存，dedup 后仍保留两个不同 code
    assert extract_metric_names("最近7天播放量走势", CATALOG, al) == ["total_plays"]
    # 多指标：播放量（catalog）+ 点赞数（别名）
    assert set(extract_metric_names("播放量和点赞数分别是多少", CATALOG, al)) == {"total_plays", "total_likes"}


def test_longest_match_priority():
    al = _aliases()
    # "播放走势"（别名）优先于任何短词；"播放时长"（catalog 精确）不受别名干扰
    assert extract_metric_names("各分类播放走势", CATALOG, al) == ["total_plays"]
    assert extract_metric_names("各分类播放时长", CATALOG, al) == ["total_play_duration"]


# ------------------------------------------------------------------ metrics_consistent 双保险
def test_metrics_consistent_alias_passes():
    al = _aliases()
    entry = _entry("对比美食和游戏分类的播放趋势", ["total_plays"])
    assert metrics_consistent("对比美食和游戏分类的播放趋势", entry, CATALOG, al) is True


def test_metrics_consistent_alias_mismatch_still_blocks():
    al = _aliases()
    entry = _entry("最近7天播放量是多少", ["total_plays"])
    # "点赞数"（别名）→ total_likes ≠ stored total_plays → 仍拦（双保险）
    assert metrics_consistent("最近7天点赞数是多少", entry, CATALOG, al) is False


def test_metrics_consistent_unresolvable_with_aliases_blocks():
    al = _aliases()
    entry = _entry("哪些视频最受欢迎", ["total_plays"])
    # 别名也匹配不到 → 不直通（降级 inject，P2-3 收紧不变）
    assert metrics_consistent("哪些视频最受欢迎", entry, CATALOG, al) is False


def test_hit_allowed_alias_passthrough():
    al = _aliases()
    entry = _entry("对比美食和游戏分类的播放趋势", ["total_plays"])
    assert hit_allowed("对比美食和游戏分类的播放趋势", entry, CATALOG, al) is True
    # 毒化：条目是播放量，问题用别名指向点赞 → 拦
    poison = _entry("最近7天点赞数是多少", ["total_plays"])
    assert hit_allowed("最近7天点赞数是多少", poison, CATALOG, al) is False


# ------------------------------------------------------------------ 2.x 指标 ID 表达指纹（可选增强）
def _fp_entries():
    """模拟写路径沉淀条目（norm_question 按 metric_codes 归属）。"""
    from app.memory.retriever import normalize_question

    class _E:
        def __init__(self, q, codes):
            self.norm_question = normalize_question(q)
            self.metric_codes = codes

    return [
        _E("对比美食和游戏分类的播放趋势", ["total_plays"]),
        _E("统计各分类总播放量", ["total_plays"]),
        _E("各分类点赞量趋势", ["total_likes"]),
        _E("游戏区完播表现怎么样", ["completion_rate"]),
    ]


@pytest.mark.asyncio
async def test_fingerprint_build_phrases_per_id():
    from app.memory.metric_ids import MetricIdFingerprint
    from tests.test_hybrid_retriever import CharBagProvider

    fp = MetricIdFingerprint(CATALOG, entries=_fp_entries(), provider=CharBagProvider())
    assert "total_plays" in fp._phrases
    assert "播放量" in fp._phrases["total_plays"]          # catalog 名
    assert any("播放趋势" in p for p in fp._phrases["total_plays"])  # 沉淀表达
    assert "completion_rate" in fp._phrases


@pytest.mark.asyncio
async def test_fingerprint_candidate_ids_embeddings():
    from app.memory.metric_ids import MetricIdFingerprint
    from tests.test_hybrid_retriever import CharBagProvider

    fp = MetricIdFingerprint(CATALOG, entries=_fp_entries(), provider=CharBagProvider(), threshold=0.5)
    ids = await fp.candidate_ids("对比美食和游戏分类的播放趋势")
    assert "total_plays" in ids
    likes = await fp.candidate_ids("各分类点赞量趋势")
    assert "total_likes" in likes


@pytest.mark.asyncio
async def test_fingerprint_poison_not_misassigned():
    """毒化：点赞量问题不得归入 total_plays（泛化防御，字符袋/向量下点赞 vs 播放区分）。"""
    from app.memory.metric_ids import MetricIdFingerprint
    from tests.test_hybrid_retriever import CharBagProvider

    fp = MetricIdFingerprint(CATALOG, entries=_fp_entries(), provider=CharBagProvider(), threshold=0.5)
    ids = await fp.candidate_ids("最近7天点赞量是多少")
    assert "total_plays" not in ids or "total_likes" in ids  # 不得单独误归 total_plays


@pytest.mark.asyncio
async def test_fingerprint_difflib_fallback():
    """provider 不可用 → difflib 降级（确定性，行为不劣于现状）。"""
    from app.memory.metric_ids import MetricIdFingerprint

    class _NoProvider:
        def available(self):
            return False

        async def embed(self, text):  # pragma: no cover
            return None

    fp = MetricIdFingerprint(CATALOG, entries=_fp_entries(), provider=_NoProvider(), threshold=0.5)
    ids = await fp.candidate_ids("对比美食和游戏分类的播放趋势")
    assert "total_plays" in ids
