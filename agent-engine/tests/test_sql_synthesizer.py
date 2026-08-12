from app.synthesis.sql_synthesizer import SynthesisError, synthesize

METRIC_DEFS = {
    "total_plays": {
        "metricCode": "total_plays",
        "formula": "total_plays",
        "sourceTable": "metric_daily",
        "timeField": "date",
        "factFormula": "COUNT(*)",
        "factEventFilter": "event_type = 'play'",
    },
    "completion_rate": {
        "metricCode": "completion_rate",
        "formula": "AVG(completion_rate)",
        "sourceTable": "play_detail",
        "timeField": "created_at",
    },
}


def _intent(**overrides):
    base = {
        "intent": "aggregate",
        "metrics": ["total_plays"],
        "dimensions": [],
        "time_range": {"type": "none", "granularity": None},
        "filters": [],
        "ordering": None,
    }
    base.update(overrides)
    return base


def test_same_intent_yields_same_sql():
    intent = _intent(intent="trend", dimensions=["category"])
    assert synthesize(intent, METRIC_DEFS) == synthesize(intent, METRIC_DEFS)


def test_trend_by_category_on_metric_daily():
    intent = _intent(intent="trend", dimensions=["category"])
    sql = synthesize(intent, METRIC_DEFS)
    assert "SELECT md.date AS date, md.category AS category, total_plays AS total_plays FROM md" in sql
    assert "GROUP BY md.date, md.category" in sql
    assert "ORDER BY md.date" in sql


def test_aggregate_by_category_wraps_sum():
    intent = _intent(intent="aggregate", dimensions=["category"])
    sql = synthesize(intent, METRIC_DEFS)
    assert "SUM(total_plays) AS total_plays" in sql
    assert "GROUP BY md.category" in sql


def test_ranking_uses_fact_table():
    intent = _intent(
        intent="ranking",
        dimensions=["content"],
        ordering={"field": "total_plays", "direction": "desc", "limit": 10},
    )
    sql = synthesize(intent, METRIC_DEFS)
    assert "FROM ubf" in sql
    assert "event_type = 'play'" in sql
    assert "GROUP BY ubf.content_id" in sql
    assert "ORDER BY COUNT(*) DESC LIMIT 10" in sql


def test_comparison_generates_in_filter():
    intent = _intent(
        intent="trend",
        dimensions=["category"],
        filters=[{"field": "category", "op": "in", "value": ["美食", "游戏"]}],
    )
    sql = synthesize(intent, METRIC_DEFS)
    assert "md.category IN ('美食', '游戏')" in sql


def test_absolute_time_range_between():
    intent = _intent(
        intent="trend",
        time_range={
            "type": "absolute",
            "absolute": {"start": "2023-10-01", "end": "2023-10-07"},
            "granularity": "day",
        },
    )
    sql = synthesize(intent, METRIC_DEFS)
    assert "md.date BETWEEN '2023-10-01' AND '2023-10-07 23:59:59'" in sql


def test_detail_intent_select_star():
    intent = _intent(intent="detail", ordering={"limit": 50})
    sql = synthesize(intent, METRIC_DEFS)
    assert sql.startswith("SELECT * FROM md LIMIT 50")


def test_unsupported_multi_metric_raises():
    intent = _intent(metrics=["total_plays", "total_likes"])
    try:
        synthesize(intent, METRIC_DEFS)
    except SynthesisError:
        return
    raise AssertionError("expected SynthesisError for multi-metric intent")
