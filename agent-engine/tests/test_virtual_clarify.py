"""metric-alias：虚拟澄清实验纯函数单测（task 3.3）。"""
import json
from pathlib import Path

from app.eval.runner import (
    _clarify_band_report,
    _clarify_decision,
    _virtual_clarify_metrics,
)
from app.memory.aliases import get_aliases, reset_aliases

ROOT = Path(__file__).resolve().parents[2]
CATALOG = json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text())


def _aliases():
    reset_aliases()
    return get_aliases()


# ------------------------------------------------------------------ 3.1 歧义判定
def test_clarify_decision_low_confidence():
    al = _aliases()
    amb, reason = _clarify_decision("统计各分类总播放量",
                                      {"intent": "aggregate", "metrics": ["total_plays"], "confidence": 0.4},
                                      CATALOG, al, conf_threshold=0.7)
    assert amb is True and "low_confidence" in reason


def test_clarify_decision_multi_metric_candidates():
    al = _aliases()
    # "播放量和点赞数" 别名/catalog 命中 2 个 ID → 多指标候选歧义
    amb, reason = _clarify_decision("播放量和点赞数分别是多少",
                                    {"intent": "aggregate", "metrics": ["total_plays"], "confidence": 0.9},
                                    CATALOG, al, conf_threshold=0.7)
    assert amb is True and "multi_metric_candidates" in reason


def test_clarify_decision_not_ambiguous():
    al = _aliases()
    amb, _ = _clarify_decision("统计各分类总播放量",
                                    {"intent": "aggregate", "metrics": ["total_plays"], "confidence": 0.9},
                                    CATALOG, al, conf_threshold=0.7)
    assert amb is False


# ------------------------------------------------------------------ 3.2 聚合（P2-3 拆分 + 收益主指标）
def _fake_results():
    return [
        # 歧义且错（真需要澄清）：基线 L1 False，澄清后 True
        {"id": "a", "a_l1": False, "ambiguous": True, "clarified_l1": True, "band": "miss"},
        # 歧义但对（不需要澄清）：基线 L1 True
        {"id": "b", "a_l1": True, "ambiguous": True, "clarified_l1": True, "band": "miss"},
        # 非歧义且对
        {"id": "c", "a_l1": True, "ambiguous": False, "clarified_l1": True, "band": "miss"},
        {"id": "d", "a_l1": True, "ambiguous": False, "clarified_l1": True, "band": "miss"},
    ]


def test_virtual_clarify_metrics_splits_ambiguous():
    m = _virtual_clarify_metrics(_fake_results(), conf_threshold=0.7)
    assert m["potential_clarify_rate"] == "2/4"
    assert m["ambiguous_error"] == "1/4"     # 歧义且错
    assert m["ambiguous_correct"] == "1/4"   # 歧义但对
    assert m["baseline_l1"] == 0.75
    assert m["clarified_l1"] == 1.0
    assert m["virtual_gain"] == 0.25         # 主指标


# ------------------------------------------------------------------ 3.2 band 分层（P2-1）
def test_clarify_band_report_only_hit_inject():
    results = [
        {"band": "hit", "ambiguous_baseline": True, "ambiguous_memory": False},   # 记忆解决
        {"band": "hit", "ambiguous_baseline": True, "ambiguous_memory": True},    # 记忆未解决
        {"band": "inject", "ambiguous_baseline": True, "ambiguous_memory": False},
        {"band": "miss", "ambiguous_baseline": True, "ambiguous_memory": True},   # 记忆不可达
    ]
    rep = _clarify_band_report(results)
    assert rep["hit"]["baseline_ambiguous"] == "2/2"
    assert rep["hit"]["memory_ambiguous"] == "1/2"
    assert rep["inject"]["memory_ambiguous"] == "0/1"
    assert rep["miss"]["memory_ambiguous"] == "1/1"  # 单独报记忆不可达，不与可达项混淆
