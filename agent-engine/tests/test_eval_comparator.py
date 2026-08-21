from app.eval.comparator import aggregate_scores, compare_spec

EVAL_DATE = "2023-10-14"

GOLDEN_TREND = {
    "intent": "trend",
    "metrics": ["total_plays"],
    "dimensions": ["category"],
    "time_range": {"type": "none", "granularity": "day"},
    "filters": [],
    "ordering": None,
}


def _actual(**overrides):
    base = {
        "intent": "trend",
        "metrics": ["total_plays"],
        "dimensions": ["category"],
        "time_range": {"type": "none", "granularity": "day"},
        "filters": [],
        "ordering": None,
    }
    base.update(overrides)
    return base


def test_exact_match_all_fields_ok():
    score = compare_spec(_actual(), GOLDEN_TREND, EVAL_DATE)
    assert score is not None
    assert score.matched is True
    assert score.core_ok is True
    assert score.field_hits == score.field_total == 6


def test_metric_alias_normalized():
    actual = _actual(metrics=["播放量"])
    score = compare_spec(actual, GOLDEN_TREND, EVAL_DATE)
    assert score.core_ok is True


def test_dimension_order_ignored():
    golden = dict(GOLDEN_TREND, dimensions=["date", "category"])
    actual = _actual(dimensions=["category", "date"])
    score = compare_spec(actual, golden, EVAL_DATE)
    assert score.fields["dimensions"] is True


def test_time_range_tolerance_within_one_day():
    golden = {
        "intent": "trend",
        "metrics": ["total_plays"],
        "dimensions": [],
        "time_range": {
            "type": "relative",
            "relative": {"amount": 7, "unit": "day"},
            "granularity": "day",
        },
        "filters": [],
        "ordering": None,
    }
    # golden eval_date expands 最近7天 to [10-08, 10-14] (6 days);
    # agent resolved [10-09, 10-14] (5 days): same end, length diff = 1 -> ok
    actual = _actual(
        dimensions=[],
        time_range={
            "type": "absolute",
            "absolute": {"start": "2023-10-09", "end": "2023-10-14"},
            "granularity": "day",
        },
    )
    score = compare_spec(actual, golden, EVAL_DATE)
    assert score.fields["time_range"] is True


def test_extra_time_constraint_is_mismatch():
    # golden: no time range; agent adds one -> mismatch
    actual = _actual(
        time_range={
            "type": "absolute",
            "absolute": {"start": "2023-10-01", "end": "2023-10-07"},
            "granularity": "day",
        }
    )
    score = compare_spec(actual, GOLDEN_TREND, EVAL_DATE)
    assert score.fields["time_range"] is False


def test_filter_misclassified_as_dimension():
    # golden: 美食 as filter; agent put it in dimensions -> filter mismatch + dimension mismatch
    golden = {
        "intent": "aggregate",
        "metrics": ["total_plays"],
        "dimensions": [],
        "time_range": {"type": "none", "granularity": None},
        "filters": [{"field": "category", "op": "=", "value": "美食"}],
        "ordering": None,
    }
    actual = {
        "intent": "aggregate",
        "metrics": ["total_plays"],
        "dimensions": ["category"],
        "time_range": {"type": "none", "granularity": None},
        "filters": [],
        "ordering": None,
    }
    score = compare_spec(actual, golden, EVAL_DATE)
    assert score.fields["dimensions"] is False
    assert score.fields["filters"] is False


def test_metric_comparison_filter_operators_are_compared():
    golden = dict(
        GOLDEN_TREND,
        intent="aggregate",
        dimensions=["creator"],
        filters=[{"field": "completion_rate", "op": ">=", "value": 50}],
        time_range={"type": "none", "granularity": None},
        ordering=None,
    )
    assert compare_spec(_actual(
        intent="aggregate",
        dimensions=["creator"],
        filters=[{"field": "completion_rate", "op": ">=", "value": 50}],
        time_range={"type": "none", "granularity": None},
        ordering=None,
    ), golden, EVAL_DATE).fields["filters"] is True
    assert compare_spec(_actual(
        intent="aggregate",
        dimensions=["creator"],
        filters=[{"field": "completion_rate", "op": ">", "value": 50}],
        time_range={"type": "none", "granularity": None},
        ordering=None,
    ), golden, EVAL_DATE).fields["filters"] is False


def test_unresolved_intent_scores_zero():
    score = compare_spec(None, GOLDEN_TREND, EVAL_DATE)
    assert score.matched is False
    assert score.core_ok is False
    assert score.field_hits == 0


def test_open_case_returns_none():
    assert compare_spec(_actual(), None, EVAL_DATE) is None


def test_aggregate_scores_four_layers():
    scores = [
        compare_spec(_actual(), GOLDEN_TREND, EVAL_DATE),
        compare_spec(_actual(metrics=["total_likes"]), GOLDEN_TREND, EVAL_DATE),
        None,
    ]
    agg = aggregate_scores(scores)
    assert agg["core"] == 0.5
    assert agg["strict"] == 0.5
    assert 0.0 < agg["avg_field"] < 1.0
    assert agg["metrics"] == 0.5
