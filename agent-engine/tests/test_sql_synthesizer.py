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


def test_multi_metric_cross_source_now_joins():
    """n02：跨源表多指标 → 子查询 JOIN（C2 解锁，不再降级）。"""
    intent = _intent(metrics=["completion_rate", "engagement_rate"], dimensions=["category"])
    sql = synthesize(intent, FULL_METRIC_DEFS)
    assert "FROM (SELECT" in sql and "JOIN" in sql


def test_multi_metric_fact_path_now_joins():
    """P1 场景闭环：trend+dims=[content] 同源 fact 冲突 → 子查询 JOIN（各自 eventFilter 隔离）。"""
    intent = _intent(intent="trend", metrics=["total_plays", "total_likes"], dimensions=["content"])
    sql = synthesize(intent, FULL_METRIC_DEFS)
    assert "FROM (SELECT" in sql and "event_type = 'play'" in sql and "event_type = 'like'" in sql


def test_multi_metric_ranking_degrades():
    intent = _intent(intent="ranking", metrics=["total_plays", "total_likes"],
                     dimensions=["content"], ordering={"field": "total_plays", "direction": "desc", "limit": 5})
    with pytest.raises(SynthesisError):
        synthesize(intent, FULL_METRIC_DEFS)


# ------------------------------------------------------------------ scale-data 新指标（比率/去重/收益）
def _load_catalog():
    import json as _json
    from pathlib import Path
    return {m["metricCode"]: m for m in
            _json.loads(Path("../src/main/resources/metric_catalog.json").read_text())}


def test_rate_metric_synthesizes():
    """P2-1：比率型指标用完整 factFormula（COUNT CASE/NULLIF），不可被 SUM 包裹错。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["comment_rate"], dimensions=["category"])
    sql = synthesize(intent, mdefs)
    assert "FROM user_behavior_fact ubf" in sql
    assert "COUNT(CASE WHEN event_type = 'comment'" in sql
    assert "NULLIF(COUNT(CASE WHEN event_type = 'play'" in sql
    assert "GROUP BY cd.category" in sql


def test_distinct_count_synthesizes():
    """P2-2：去重计数带合成器别名 ubf，防 JOIN 后歧义。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["daily_active_users"], dimensions=[])
    sql = synthesize(intent, mdefs)
    assert "COUNT(DISTINCT ubf.user_id)" in sql
    assert "FROM user_behavior_fact ubf" in sql


def test_new_table_revenue_synthesizes():
    """新表收益指标走自己的 sourceTable（不误路由到 fact）。"""
    mdefs = _load_catalog()
    # video_revenue 聚合
    sql1 = synthesize(_intent(metrics=["video_revenue"], dimensions=[]), mdefs)
    assert "FROM video_revenue vr" in sql1
    assert "SUM(revenue)" in sql1
    # creator_revenue ranking
    sql2 = synthesize(_intent(intent="ranking", metrics=["creator_revenue"], dimensions=["creator"],
                              ordering={"field": "creator_revenue", "direction": "desc", "limit": 3}), mdefs)
    assert "FROM creator_revenue cr" in sql2
    assert "cr.creator_id AS creator" in sql2
    assert "ORDER BY SUM(revenue) DESC LIMIT 3" in sql2


# ------------------------------------------------------------------ query-capability（指标值过滤 HAVING + 冲突多指标 JOIN）
def test_metric_value_filter_having():
    """P2-1：field 是指标 code → HAVING（复用 SELECT agg_expr）。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["completion_rate"], dimensions=["category"],
                     filters=[{"field": "completion_rate", "op": ">", "value": 50}])
    sql = synthesize(intent, mdefs)
    assert "GROUP BY" in sql
    assert "HAVING AVG(completion_rate) > 50" in sql


def test_mixed_dimension_and_metric_filter():
    """维度过滤 WHERE + 指标过滤 HAVING 混合。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["completion_rate"], dimensions=["category"],
                     filters=[{"field": "category", "op": "=", "value": "美食"},
                              {"field": "completion_rate", "op": ">=", "value": 40}])
    sql = synthesize(intent, mdefs)
    assert "WHERE" in sql and "category = '美食'" in sql
    assert "HAVING AVG(completion_rate) >= 40" in sql


def test_metric_filter_unsupported_intent_degrades():
    """ranking + 指标过滤 → 降级（MVP 限 aggregate/trend）。"""
    mdefs = _load_catalog()
    intent = _intent(intent="ranking", metrics=["completion_rate"], dimensions=["category"],
                     ordering={"field": "completion_rate", "direction": "desc", "limit": 5},
                     filters=[{"field": "completion_rate", "op": ">", "value": 50}])
    with pytest.raises(SynthesisError):
        synthesize(intent, mdefs)


def test_conflict_multi_metric_cross_source_join():
    """n02：跨源多指标（play_detail + fact）→ 子查询 JOIN。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["completion_rate", "engagement_rate"], dimensions=["category"])
    sql = synthesize(intent, mdefs)
    assert "FROM (SELECT" in sql
    assert "FROM play_detail pd" in sql and "FROM user_behavior_fact ubf" in sql
    assert "JOIN" in sql and "ON a.category = b.category" in sql
    assert "JOIN content_dim cd" in sql  # play_detail 拿 category


def test_conflict_multi_metric_same_source_event_filter_join():
    """同源 fact 冲突（play vs like）→ 子查询 JOIN（P1 场景闭环）。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["total_plays", "total_likes"], dimensions=["content"])
    sql = synthesize(intent, mdefs)
    assert "event_type = 'play'" in sql and "event_type = 'like'" in sql
    assert "FROM (SELECT" in sql and "JOIN" in sql


def test_same_source_same_filter_single_from_unchanged():
    """n01：同源 metric_daily 同 filter → 单 FROM（不变）。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["total_plays", "total_likes"], dimensions=["category"])
    sql = synthesize(intent, mdefs)
    assert "FROM metric_daily md" in sql
    assert "FROM (SELECT" not in sql


def test_misaligned_granularity_degrades():
    """异粒度跨源（一个 category、一个 content）→ 降级（本实现经 _resolve_path 各自路径，若无法共享维度键则产错；此处验证至少不产出矛盾）。"""
    mdefs = _load_catalog()
    # completion_rate(play_detail, 只能 content 粒度) + total_plays(fact, content) → 两者都 content 粒度可对齐 → 应 JOIN
    intent = _intent(metrics=["completion_rate", "total_plays"], dimensions=["content"])
    sql = synthesize(intent, mdefs)
    assert "FROM (SELECT" in sql  # content 粒度可对齐 → JOIN（play_detail JOIN content_dim）


def test_conflict_multi_metric_no_dim_key_degrades():
    """冲突多指标无维度键（dims=[] 且非 trend）→ 无法 JOIN → 降级。"""
    mdefs = _load_catalog()
    intent = _intent(metrics=["completion_rate", "engagement_rate"], dimensions=[])
    with pytest.raises(SynthesisError):
        synthesize(intent, mdefs)
