"""归一化：把 golden_spec 与 agent 输出转成可比较的规范形态（纯函数）。"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

METRIC_ALIASES = {
    "播放量": "total_plays",
    "播放": "total_plays",
    "播放数": "total_plays",
    "总播放量": "total_plays",
    "播放时长": "total_play_duration",
    "观看时长": "total_play_duration",
    "点赞量": "total_likes",
    "点赞数": "total_likes",
    "点赞": "total_likes",
    "评论量": "total_comments",
    "评论数": "total_comments",
    "评论": "total_comments",
    "分享量": "total_shares",
    "分享数": "total_shares",
    "分享": "total_shares",
    "完播率": "completion_rate",
    "互动率": "engagement_rate",
}

DIMENSION_ALIASES = {
    "分类": "category",
    "类别": "category",
    "类目": "category",
    "category": "category",
    "日期": "date",
    "时间": "date",
    "天": "date",
    "date": "date",
    "内容": "content",
    "视频": "content",
    "content": "content",
    "创作者": "creator",
    "作者": "creator",
    "creator": "creator",
}

FIELD_ALIASES = {
    "分类": "category",
    "类别": "category",
    "category": "category",
    "日期": "date",
    "时间": "date",
    "date": "date",
    "created_at": "date",
    "timestamp": "date",
    "内容": "content",
    "content_id": "content",
    "content": "content",
    "创作者": "creator",
    "creator_id": "creator",
    "creator": "creator",
}

UNIT_DAYS = {"day": 1, "week": 7, "month": 30}
def normalize_metric(value: Any) -> str:
    s = str(value).strip()
    return METRIC_ALIASES.get(s, s)


def normalize_dimension(value: Any) -> str:
    s = str(value).strip().lower()
    return DIMENSION_ALIASES.get(s, s)


def normalize_field(value: Any) -> str:
    s = str(value).strip().lower()
    return FIELD_ALIASES.get(s, s)


def normalize_filter_value(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(sorted(str(v).strip() for v in value))
    if isinstance(value, (int, float)):
        return value
    return str(value).strip()


def normalize_filter(flt: dict[str, Any]) -> tuple[str, str, Any]:
    field = normalize_field(flt.get("field") or "")
    op = normalize_filter_op(flt.get("op"))
    value = normalize_filter_value(flt.get("value"))
    return (field, op, value)


def normalize_filter_op(value: Any) -> str:
    """Normalize filter operators, including metric comparisons used by HAVING.

    Unknown operators are preserved so a malformed LLM output mismatches the
    golden spec instead of being silently treated as equality.
    """
    return str(value or "=").strip().lower()


def _parse_date(value: str) -> date:
    return date.fromisoformat(str(value)[:10])


def expand_time_range(tr: dict[str, Any] | None, eval_date: str) -> tuple[str, str, str | None] | None:
    """Expand a time_range to (start, end, granularity); None = no constraint."""
    if not tr:
        return None
    ttype = tr.get("type")
    granularity = tr.get("granularity")
    if ttype == "absolute":
        absolute = tr.get("absolute") or {}
        if not absolute.get("start") or not absolute.get("end"):
            return None
        return str(absolute["start"]), str(absolute["end"]), granularity
    if ttype == "relative":
        rel = tr.get("relative") or {}
        amount = max(int(rel.get("amount") or 0), 1)
        unit = str(rel.get("unit") or "day")
        base = _parse_date(eval_date)
        end = base
        start = base - timedelta(days=amount * UNIT_DAYS.get(unit, 1) - 1)
        return start.isoformat(), end.isoformat(), granularity
    return None
