import pytest

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
    assert "SELECT md.date AS date, md.category AS category, total_plays AS total_plays FROM metric_daily md" in sql
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
    assert "FROM user_behavior_fact ubf" in sql
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
    assert sql.startswith("SELECT * FROM metric_daily md LIMIT 50")


def test_from_clause_declares_real_table_and_alias():
    """合成 SQL 的 FROM 必须含真实表名 + 别名声明（BUG-006 回归）。"""
    # metric_daily 路径
    md_sql = synthesize(_intent(intent="aggregate", dimensions=["category"]), METRIC_DEFS)
    assert "FROM metric_daily md" in md_sql
    # user_behavior_fact 路径（ranking + factFormula 触发事实表）
    ubf_sql = synthesize(
        _intent(
            intent="ranking",
            dimensions=["content"],
            ordering={"field": "total_plays", "direction": "desc", "limit": 10},
        ),
        METRIC_DEFS,
    )
    assert "FROM user_behavior_fact ubf" in ubf_sql
    # play_detail 路径（detail intent + sourceTable=play_detail）
    pd_sql = synthesize(
        _intent(intent="detail", metrics=["completion_rate"], ordering={"limit": 50}),
        METRIC_DEFS,
    )
    assert pd_sql.startswith("SELECT * FROM play_detail pd")


def test_unsupported_multi_metric_raises():
    intent = _intent(metrics=["total_plays", "total_likes"])
    try:
        synthesize(intent, METRIC_DEFS)
    except SynthesisError:
        return
    raise AssertionError("expected SynthesisError for multi-metric intent")


# ------------------------------------------------------------------ 多指标（multi-metric-synthesis）
FULL_METRIC_DEFS = {
    **METRIC_DEFS,
    "total_likes": {
        "metricCode": "total_likes", "formula": "total_likes",
        "sourceTable": "metric_daily", "timeField": "date",
        "factFormula": "COUNT(*)", "factEventFilter": "event_type = 'like'",
    },
    "engagement_rate": {
        "metricCode": "engagement_rate",
        "formula": "(SUM(CASE WHEN event_type = 'like' THEN 1 ELSE 0 END) + SUM(CASE WHEN event_type = 'comment' THEN 1 ELSE 0 END)) / NULLIF(SUM(CASE WHEN event_type = 'play' THEN 1 ELSE 0 END), 0)",
        "sourceTable": "user_behavior_fact",
    },
}


def test_multi_metric_same_source_aggregate():
    """n01：metric_daily 同源多指标聚合——单 FROM 多列，无 spurious JOIN，SUM 包裹。"""
    intent = _intent(metrics=["total_plays", "total_likes"], dimensions=["category"])
    sql = synthesize(intent, FULL_METRIC_DEFS)
    assert "FROM metric_daily md" in sql
    assert "SUM(total_plays) AS total_plays" in sql
    assert "SUM(total_likes) AS total_likes" in sql
    assert "GROUP BY md.category" in sql
    assert "JOIN" not in sql  # P2：metric_daily 的 category 无 JOIN
    assert sql.count("FROM") == 1  # 单 FROM


def test_multi_metric_same_source_trend():
    intent = _intent(intent="trend", metrics=["total_plays", "total_likes"], dimensions=["category"])
    sql = synthesize(intent, FULL_METRIC_DEFS)
    assert "md.date AS date, md.category AS category" in sql
    assert "total_plays AS total_plays, total_likes AS total_likes" in sql
    assert "GROUP BY md.date, md.category" in sql


def test_multi_metric_cross_source_degrades():
    """n02：跨源表多指标（play_detail + user_behavior_fact）→ SynthesisError（降级）。"""
    intent = _intent(metrics=["completion_rate", "engagement_rate"], dimensions=["category"])
    with pytest.raises(SynthesisError):
        synthesize(intent, FULL_METRIC_DEFS)


def test_multi_metric_fact_path_degrades():
    """P1：trend+dims=[content] 触发事实路径路由（factEventFilter 不同会空结果）→ 降级。"""
    intent = _intent(intent="trend", metrics=["total_plays", "total_likes"], dimensions=["content"])
    with pytest.raises(SynthesisError):
        synthesize(intent, FULL_METRIC_DEFS)


def test_multi_metric_ranking_degrades():
    intent = _intent(intent="ranking", metrics=["total_plays", "total_likes"],
                     dimensions=["content"], ordering={"field": "total_plays", "direction": "desc", "limit": 5})
    with pytest.raises(SynthesisError):
        synthesize(intent, FULL_METRIC_DEFS)
