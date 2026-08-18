"""real-memory-baseline：real-session 协议单测（tasks 1.3 / 2.2 / 3.2 / 4.2）。

覆盖：协议前置校验、namespace 生成、会话选择、近似问变体匹配、一致率逐字段口径、
指标聚合（x/y 原始计数 + 方向性标注）、弱验证（SQLite/Lance 持久化 close→reopen）、防污染。"""
import json
from pathlib import Path

import pytest

from app.eval.runner import (
    DEFAULT_CASES,
    _assert_real_session_valid,
    _intents_equal,
    _pick_real_sessions,
    _real_session_metrics,
    _real_session_namespace,
    _variant_for,
)
from app.memory.retriever import normalize_question
from app.memory.store import MemoryStore
from app.memory.vector_store import LanceVectorStore

SYNONYM_CASES = Path("app/eval/synonym_cases.yaml")


def _golden_cases() -> list[dict]:
    return json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))["cases"]


def _syn_cases() -> list[dict]:
    return json.loads(SYNONYM_CASES.read_text(encoding="utf-8"))["cases"]


# ------------------------------------------------------------------ 1.3 协议前置校验
def test_assert_real_session_valid_mock_llm_rejected():
    with pytest.raises(SystemExit):
        _assert_real_session_valid("mock")


def test_assert_real_session_valid_real_and_replay_ok():
    _assert_real_session_valid("real")
    _assert_real_session_valid("replay")  # cassette 回放真实响应，可沉淀


# ------------------------------------------------------------------ 1.1 namespace 生成
def test_real_session_namespace_prefix_and_date():
    ns = _real_session_namespace("2026-08-18")
    assert ns.startswith("real-2026-08-18-")
    assert ns.split("-")[-1].isdigit()  # 时间戳后缀


# ------------------------------------------------------------------ 1.2 会话选择
def test_pick_real_sessions_covers_intents_and_skips_memory_cases():
    cases = _golden_cases()
    picked = _pick_real_sessions(cases, 8)
    assert len(picked) == 8
    assert all(c.get("golden_spec") for c in picked)
    assert all(not (c.get("repeat_of") or c.get("memory_setup")) for c in picked)
    intents = {(c["golden_spec"] or {}).get("intent") for c in picked}
    assert len(intents) >= 2  # intent 多样性（detail 无 golden 用例，不强制 4 类）
    ids = [c["id"] for c in picked]
    assert len(set(ids)) == len(ids)  # 无重复


def test_pick_real_sessions_respects_count():
    picked = _pick_real_sessions(_golden_cases(), 4)
    assert len(picked) == 4


def test_variant_for_matches_easy_layer():
    syn = _syn_cases()
    v = _variant_for({"id": "c02_category_total"}, syn)
    assert v is not None
    assert any(s["source_case"] == "c02_category_total" and s["question"] == v for s in syn)
    assert _variant_for({"id": "no_such_case"}, syn) is None


# ------------------------------------------------------------------ 2.1 一致率逐字段口径
def test_intents_equal_fieldwise():
    base = {"intent": "trend", "metrics": ["total_plays"], "dimensions": ["category"],
            "time_range": {"type": "none", "granularity": "day"}, "filters": [], "ordering": None}
    assert _intents_equal(base, dict(base))
    for key in ("metrics", "dimensions"):
        diff = dict(base)
        diff[key] = ["total_likes"] if key == "metrics" else ["content"]
        assert not _intents_equal(base, diff)
    diff_tr = dict(base)
    diff_tr["time_range"] = {"type": "relative", "relative": {"days": 7}, "granularity": "day"}
    assert not _intents_equal(base, diff_tr)
    assert not _intents_equal(None, base)
    assert not _intents_equal(base, None)


# ------------------------------------------------------------------ 2.2 指标聚合（原始计数 + 方向性）
def test_real_session_metrics_raw_counts_and_direction_note():
    per = [
        {"second_hit": True, "consistent": True, "persist_ok": True,
         "first_tokens": 100, "second_tokens": 50, "variant": None} for _ in range(5)
    ] + [
        {"second_hit": False, "consistent": False, "persist_ok": False,
         "first_tokens": 100, "second_tokens": 200, "variant": "q?"} for _ in range(2)
    ]
    m = _real_session_metrics(per, "mock", "real-x")
    assert m["real_hit_rate"] == "5/7"          # x/y 原始计数
    assert m["real_consistency"] == "5/7"
    assert m["real_persist_hits"] == "5/7"      # mock 弱验证
    assert m["real_hit_rate_pct"] == pytest.approx(5 / 7)
    assert m["variant_total"] == 2
    assert m["session_total"] == 7
    assert "方向性" in m["direction_note"]       # N 量级方向性标注
    m_real = _real_session_metrics(per, "real", "real-x")
    assert m_real["real_persist_hits"] == "N/A (real: 强验证=重启服务器，留联调)"


# ------------------------------------------------------------------ 3.2 弱验证：close → reopen 持久化
@pytest.mark.asyncio
async def test_persist_weak_sqlite(tmp_path):
    db = str(tmp_path / "m.sqlite")
    store = MemoryStore(db)
    await store.init()
    await store.upsert(normalize_question("分析各分类播放量趋势"), {"intent": "trend"},
                       ["total_plays"], "h", namespace="real-2026-08-18-1")
    await store.close()
    store2 = MemoryStore(db)
    await store2.init()
    rows = await store2.all(namespace="real-2026-08-18-1")
    assert len(rows) == 1
    assert rows[0].resolved_intent["intent"] == "trend"
    await store2.close()


@pytest.mark.asyncio
async def test_persist_weak_lance(tmp_path):
    from tests.test_hybrid_retriever import CharBagProvider

    path = str(tmp_path / "m.lance")
    store = LanceVectorStore(path, provider=CharBagProvider(), embedding_model="test")
    await store.init()
    await store.upsert(normalize_question("统计各分类总播放量"), {"intent": "aggregate"},
                       ["total_plays"], "h", namespace="real-2026-08-18-1")
    await store.close()
    store2 = LanceVectorStore(path, provider=CharBagProvider(), embedding_model="test")
    await store2.init()
    rows = await store2.all(namespace="real-2026-08-18-1")
    assert len(rows) == 1
    assert rows[0].resolved_intent["intent"] == "aggregate"
    await store2.close()


# ------------------------------------------------------------------ 4.2 防污染：real-* 不写 default
@pytest.mark.asyncio
async def test_real_namespace_does_not_touch_default():
    store = MemoryStore(":memory:")
    await store.init()
    try:
        await store.upsert(normalize_question("最近7天播放量是多少"), {"intent": "trend"},
                           ["total_plays"], "h", namespace="real-2026-08-18-1")
        assert await store.all(namespace="default") == []
        assert len(await store.all(namespace="real-2026-08-18-1")) == 1
        # 显式 default 联调开关可写
        await store.upsert(normalize_question("完播率是多少"), {"intent": "aggregate"},
                           ["completion_rate"], "h", namespace="default")
        assert len(await store.all(namespace="default")) == 1
    finally:
        await store.close()
