"""time_expand：相对时间确定性展开（relative → absolute）。

- 锚点 = 数据末日（seed 42 确定性，R1 可复现）。
- 含端点语义：最近 N 天 = [锚点 - (N-1), 锚点]。
- unit：day / week（month 近似 30 天，标注边界）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}  # month 近似 30 天（MVP 边界）


def normalize_anchor_date(value: Any) -> str:
    """平台 DATE/datetime/ISO 值 → 规范 YYYY-MM-DD；非法值 fail-closed。"""
    if value is None:
        raise ValueError("ANCHOR_DATE_MISSING")
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text:
        raise ValueError("ANCHOR_DATE_MISSING")
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        pass
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.date().isoformat()
    except ValueError as exc:
        raise ValueError(f"ANCHOR_DATE_INVALID: {text}") from exc


def time_expand(relative: dict[str, Any], anchor_date: str) -> dict[str, Any]:
    """relative {amount, unit} + anchor_date → absolute {type, start, end, granularity}。"""
    amount = int(relative.get("amount") or 1)
    unit = str(relative.get("unit") or "day")
    if unit not in _UNIT_DAYS:
        raise ValueError(f"unsupported relative unit: {unit}")
    days = _UNIT_DAYS[unit] * amount
    anchor = date.fromisoformat(anchor_date)
    start = anchor - timedelta(days=days - 1)  # 含端点
    return {
        "type": "absolute",
        "absolute": {"start": start.isoformat(), "end": anchor.isoformat()},
        "granularity": relative.get("granularity"),
    }
