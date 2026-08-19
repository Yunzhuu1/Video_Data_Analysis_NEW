"""time_expand：相对时间确定性展开（relative → absolute）。

- 锚点 = 数据末日（seed 42 确定性，R1 可复现）。
- 含端点语义：最近 N 天 = [锚点 - (N-1), 锚点]。
- unit：day / week（month 近似 30 天，标注边界）。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

_UNIT_DAYS = {"day": 1, "week": 7, "month": 30}  # month 近似 30 天（MVP 边界）


def time_expand(relative: dict[str, Any], anchor_date: str) -> dict[str, Any]:
    """relative {amount, unit} + anchor_date → absolute {type, start, end, granularity}。"""
    amount = int(relative.get("amount") or 1)
    unit = str(relative.get("unit") or "day")
    if unit not in _UNIT_DAYS:
        raise ValueError(f"unsupported relative unit: {unit}")
    days = _UNIT_DAYS[unit] * amount
    anchor = date.fromisoformat(str(anchor_date))
    start = anchor - timedelta(days=days - 1)  # 含端点
    return {
        "type": "absolute",
        "absolute": {"start": start.isoformat(), "end": anchor.isoformat()},
        "granularity": relative.get("granularity"),
    }
