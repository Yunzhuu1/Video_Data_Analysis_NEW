"""relative-time-synthesis：time_expand 单测（含端点/unit 换算/边界）。"""
import pytest

from app.synthesis.time_expand import time_expand


def test_last7days_inclusive_endpoints():
    r = time_expand({"amount": 7, "unit": "day"}, "2023-10-31")
    assert r["type"] == "absolute"
    assert r["absolute"]["start"] == "2023-10-25"  # 末日往前 6 天（含端点共 7 天）
    assert r["absolute"]["end"] == "2023-10-31"


def test_last30days():
    r = time_expand({"amount": 30, "unit": "day"}, "2023-10-31")
    assert r["absolute"]["start"] == "2023-10-02"
    assert r["absolute"]["end"] == "2023-10-31"


def test_one_week_equals_seven_days():
    r = time_expand({"amount": 1, "unit": "week"}, "2023-10-31")
    assert r["absolute"]["start"] == "2023-10-25"
    assert r["absolute"]["end"] == "2023-10-31"


def test_yesterday_to_today_amount2():
    r = time_expand({"amount": 2, "unit": "day"}, "2023-10-31")
    assert r["absolute"]["start"] == "2023-10-30"
    assert r["absolute"]["end"] == "2023-10-31"


def test_amount_one_single_day():
    r = time_expand({"amount": 1, "unit": "day"}, "2023-10-31")
    assert r["absolute"]["start"] == "2023-10-31"
    assert r["absolute"]["end"] == "2023-10-31"


def test_granularity_passthrough():
    r = time_expand({"amount": 7, "unit": "day", "granularity": "day"}, "2023-10-31")
    assert r["granularity"] == "day"


def test_unsupported_unit_raises():
    with pytest.raises(ValueError):
        time_expand({"amount": 1, "unit": "year"}, "2023-10-31")
