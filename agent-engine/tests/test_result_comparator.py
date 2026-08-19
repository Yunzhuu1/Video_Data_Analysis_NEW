"""eval-result-grading：ResultComparator 单测（exact/exact_per_key/trend_pattern/top_set + 边界）。"""
from app.eval.result_comparator import check_result


def test_exact_pass_and_fail():
    rows = [{"category": "美食", "total_plays": 12345}]
    assert check_result(rows, {"type": "exact", "value": 12345, "tolerance": 0.01}, "aggregate").passed is True
    assert check_result(rows, {"type": "exact", "value": 13000, "tolerance": 0.01}, "aggregate").passed is False


def test_exact_empty_rows_fails():
    r = check_result([], {"type": "exact", "value": 1}, "aggregate")
    assert r is not None and r.passed is False


def test_exact_per_key_pass_and_missing():
    rows = [
        {"category": "美食", "total_plays": 1000},
        {"category": "游戏", "total_plays": 2000},
    ]
    exp = {"type": "exact_per_key", "values": {"美食": 1000, "游戏": 2000}, "tolerance": 0.01}
    assert check_result(rows, exp, "aggregate").passed is True
    exp_bad = {"type": "exact_per_key", "values": {"美食": 1000, "美妆": 999}, "tolerance": 0.01}
    r = check_result(rows, exp_bad, "aggregate")
    assert r is not None and r.passed is False and "美妆" in r.detail


def test_trend_pattern_single_series():
    rows = [
        {"date": "2023-10-01", "total_plays": 100},
        {"date": "2023-10-02", "total_plays": 200},   # up
        {"date": "2023-10-03", "total_plays": 50},    # down
    ]
    exp = {"type": "trend_pattern", "points": [
        {"date": "2023-10-02", "direction": "up"},
        {"date": "2023-10-03", "direction": "down"},
    ]}
    assert check_result(rows, exp, "trend").passed is True
    exp_bad = {"type": "trend_pattern", "points": [
        {"date": "2023-10-02", "direction": "down"},
    ]}
    assert check_result(rows, exp_bad, "trend").passed is False


def test_trend_pattern_multi_series():
    rows = [
        {"date": "2023-10-01", "category": "美食", "total_plays": 100},
        {"date": "2023-10-02", "category": "美食", "total_plays": 300},   # spike
        {"date": "2023-10-01", "category": "游戏", "total_plays": 100},
        {"date": "2023-10-02", "category": "游戏", "total_plays": 150},   # up
    ]
    exp = {"type": "trend_pattern", "series": {
        "美食": [{"date": "2023-10-02", "direction": "up", "magnitude": "spike"}],
        "游戏": [{"date": "2023-10-02", "direction": "up"}],
    }}
    assert check_result(rows, exp, "trend").passed is True
    exp_bad = {"type": "trend_pattern", "series": {
        "美食": [{"date": "2023-10-02", "direction": "down"}],
    }}
    assert check_result(rows, exp_bad, "trend").passed is False


def test_top_set_set_and_order():
    rows = [{"content_id": f"content_{i}"} for i in (3, 4, 1)]
    exp = {"type": "top_set", "items": ["content_1", "content_3", "content_4"], "ordered": False}
    assert check_result(rows, exp, "ranking").passed is True
    exp_ordered = {"type": "top_set", "items": ["content_3", "content_4", "content_1"], "ordered": True}
    assert check_result(rows, exp_ordered, "ranking").passed is True
    exp_wrong_order = {"type": "top_set", "items": ["content_3", "content_1", "content_4"], "ordered": True}
    assert check_result(rows, exp_wrong_order, "ranking").passed is False


def test_top_set_missing_item():
    rows = [{"content_id": "content_1"}]
    exp = {"type": "top_set", "items": ["content_1", "content_2"]}
    assert check_result(rows, exp, "ranking").passed is False


def test_unsupported_type_returns_none():
    assert check_result([], {"type": "unknown"}, "detail") is None
    assert check_result([], None, "detail") is None
