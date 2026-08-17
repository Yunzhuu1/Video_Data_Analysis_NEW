from app.agents.semantic_resolver import SemanticResolver


def _intent(**overrides):
    base = {
        "intent": "trend",
        "metrics": ["total_plays"],
        "dimensions": [],
        "time_range": {"type": "none", "granularity": None},
        "filters": [],
        "ordering": None,
        "confidence": 0.9,
        "coverage": "full",
    }
    base.update(overrides)
    return base


def test_date_removed_from_dimensions():
    # c07/c12/c13 主失败模式：date 误入 dimensions → 清洗
    intent = _intent(dimensions=["date", "category"],
                     filters=[{"field": "category", "op": "in", "value": ["美食", "游戏"]}])
    out = SemanticResolver._apply_fallbacks("对比美食和游戏分类的播放趋势", intent)
    assert "date" not in out["dimensions"]
    assert out["dimensions"] == ["category"]


def test_category_filled_for_gefenlei_pattern():
    # c01 偶发兜底：含"各分类"且无维度、无 category filter → 补 category
    out = SemanticResolver._apply_fallbacks("分析各分类播放量趋势", _intent())
    assert out["dimensions"] == ["category"]


def test_no_fill_when_category_filter_exists():
    # "美食类"已有 category filter，不得补 category 维度
    intent = _intent(filters=[{"field": "category", "op": "=", "value": "美食"}])
    out = SemanticResolver._apply_fallbacks("美食类视频播放量趋势", intent)
    assert out["dimensions"] == []


def test_day_granularity_only_with_keyword():
    # "最近7天每天播放量" → trend + 每天 → 补 day
    out = SemanticResolver._apply_fallbacks(
        "最近7天每天播放量是多少",
        _intent(time_range={"type": "relative", "relative": {"amount": 7, "unit": "day"}, "granularity": None}),
    )
    assert out["time_range"]["granularity"] == "day"


def test_no_day_fill_without_keyword():
    # "最近4周每周播放量"（无 每天/每日）→ 不强制补 day
    out = SemanticResolver._apply_fallbacks(
        "最近4周每周播放量",
        _intent(time_range={"type": "relative", "relative": {"amount": 4, "unit": "week"}, "granularity": None}),
    )
    assert out["time_range"]["granularity"] is None
