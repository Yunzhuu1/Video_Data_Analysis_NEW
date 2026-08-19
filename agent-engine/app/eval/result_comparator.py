"""ResultComparator：结果级断言（eval-result-grading）。

按 expected.type 分层断言真实执行结果 rows：
- exact          ：无维度单行聚合，数值 + 相对容差
- exact_per_key  ：带维度多行聚合，{key: value} 映射 + 容差
- trend_pattern  ：时间序列方向/模式（单序列 points 或多序列 series）
- top_set        ：top-N 集合（必选）+ 可选顺序

返回 ResultCheck；expected.type 不支持（detail/歧义）返回 None。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_TOLERANCE = 0.01  # 相对容差 1%
SPIKE_RATIO = 0.5  # 相对前点增长 >50% 记为 spike
DROP_RATIO = 0.4   # 相对前点下降 >40% 记为 drop


@dataclass
class ResultCheck:
    passed: bool
    kind: str
    detail: str


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tol(expected: dict[str, Any]) -> float:
    return float(expected.get("tolerance") or DEFAULT_TOLERANCE)


def _near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol * max(1.0, abs(b))


def _check_exact(rows: list[dict[str, Any]], expected: dict[str, Any]) -> ResultCheck:
    if not rows:
        return ResultCheck(False, "exact", "no rows")
    # 取第一个数值列（排除 key 列后）
    first = rows[0]
    numeric_cols = [k for k, v in first.items() if _num(v) is not None]
    if not numeric_cols:
        return ResultCheck(False, "exact", f"no numeric column in {first}")
    col = numeric_cols[0]
    actual = _num(first[col])
    want = _num(expected.get("value"))
    if actual is None or want is None:
        return ResultCheck(False, "exact", f"non-numeric actual={first[col]} want={expected.get('value')}")
    ok = _near(actual, want, _tol(expected))
    return ResultCheck(ok, "exact", f"{col}={actual} vs {want} (tol={_tol(expected)})")


def _check_exact_per_key(rows: list[dict[str, Any]], expected: dict[str, Any]) -> ResultCheck:
    values: dict[str, Any] = expected.get("values") or {}
    tol = _tol(expected)
    if not rows:
        return ResultCheck(False, "exact_per_key", "no rows")
    keys_col = [k for k in rows[0] if k not in values]  # 非 values 键的列作为 key 列
    if not keys_col:
        return ResultCheck(False, "exact_per_key", "no key column")
    key_col = keys_col[0]
    num_col = next((k for k in rows[0] if _num(rows[0][k]) is not None and k != key_col), None)
    if num_col is None:
        return ResultCheck(False, "exact_per_key", "no numeric column")
    actual_map = {str(r[key_col]): _num(r[num_col]) for r in rows}
    mismatches = []
    for key, want_v in values.items():
        act = actual_map.get(str(key))
        if act is None:
            mismatches.append(f"{key}:missing")
        elif not _near(act, float(want_v), tol):
            mismatches.append(f"{key}:{act} vs {want_v}")
    ok = not mismatches
    return ResultCheck(ok, "exact_per_key", "; ".join(mismatches) if mismatches else "all keys match")


def _direction(prev: float, cur: float) -> tuple[str, str | None]:
    if cur > prev:
        ratio = (cur - prev) / prev if prev else 0.0
        return "up", ("spike" if ratio >= SPIKE_RATIO else None)
    if cur < prev:
        ratio = (prev - cur) / prev if prev else 0.0
        return "down", ("drop" if ratio >= DROP_RATIO else None)
    return "flat", None


def _check_series(rows: list[dict[str, Any]], date_col: str, val_col: str,
                  points: list[dict[str, Any]]) -> ResultCheck:
    """单序列 trend_pattern：按日期升序，逐点断言方向/模式。"""
    try:
        ordered = sorted(rows, key=lambda r: str(r[date_col]))
    except KeyError as exc:
        return ResultCheck(False, "trend_pattern", f"missing col {exc}")
    values = {str(r[date_col]): _num(r[val_col]) for r in ordered}
    problems = []
    for pt in points:
        date = str(pt.get("date") or "")
        want_dir = str(pt.get("direction") or "")
        want_mag = pt.get("magnitude")
        cur = values.get(date)
        if cur is None:
            problems.append(f"{date}:missing")
            continue
        # 找前一个已知值（按排序取前值）
        prev = None
        for r in ordered:
            if str(r[date_col]) == date:
                break
            v = _num(r[val_col])
            if v is not None:
                prev = v
        if prev is None:
            continue  # 无前值无法判方向，跳过
        d, mag = _direction(prev, cur)
        if d != want_dir:
            problems.append(f"{date}:dir={d} want {want_dir}")
        elif want_mag and mag != want_mag:
            problems.append(f"{date}:mag={mag} want {want_mag}")
    ok = not problems
    return ResultCheck(ok, "trend_pattern", "; ".join(problems) if problems else "points match")


def _check_trend_pattern(rows: list[dict[str, Any]], expected: dict[str, Any]) -> ResultCheck:
    if not rows:
        return ResultCheck(False, "trend_pattern", "no rows")
    series = expected.get("series")
    if series:  # 多序列：按 key 分组断言
        key_col = next((k for k in rows[0] if not isinstance(rows[0][k], (int, float)) or k not in ("date",)), None)
        # key 列 = 非数值列且非 date；数值列 = 唯一数值列
        num_col = next((k for k, v in rows[0].items() if _num(v) is not None and k != "date"), None)
        key_col = next((k for k, v in rows[0].items() if _num(v) is None and k != "date"), None)
        if num_col is None or key_col is None:
            return ResultCheck(False, "trend_pattern", "cannot detect key/numeric columns")
        problems = []
        for key, pts in series.items():
            sub = [r for r in rows if str(r[key_col]) == str(key)]
            if not sub:
                problems.append(f"{key}:missing")
                continue
            rc = _check_series(sub, "date", num_col, pts)
            if not rc.passed:
                problems.append(f"{key}:{rc.detail}")
        ok = not problems
        return ResultCheck(ok, "trend_pattern", "; ".join(problems) if problems else "series match")
    # 单序列
    num_col = next((k for k, v in rows[0].items() if _num(v) is not None and k != "date"), None)
    if num_col is None:
        return ResultCheck(False, "trend_pattern", "no numeric column")
    return _check_series(rows, "date", num_col, expected.get("points") or [])


def _check_top_set(rows: list[dict[str, Any]], expected: dict[str, Any]) -> ResultCheck:
    if not rows:
        return ResultCheck(False, "top_set", "no rows")
    items = [str(x) for x in (expected.get("items") or [])]
    key_col = next((k for k, v in rows[0].items() if not isinstance(v, (int, float))), None)
    if key_col is None:
        return ResultCheck(False, "top_set", "no key column")
    actual = [str(r[key_col]) for r in rows]
    missing = [x for x in items if x not in actual]
    extra = [x for x in actual if x not in items]
    if missing or extra:
        return ResultCheck(False, "top_set", f"missing={missing} extra={extra}")
    if expected.get("ordered"):
        want_seq = items[: len(actual)]
        if actual != want_seq:
            return ResultCheck(False, "top_set", f"order {actual} != {want_seq}")
    return ResultCheck(True, "top_set", f"{len(actual)} items match")


def check_result(rows: list[dict[str, Any]], expected: dict[str, Any],
                 intent: str | None = None) -> ResultCheck | None:
    """结果级断言入口。expected.type 不支持（detail/歧义）返回 None（R1=N/A）。"""
    kind = str((expected or {}).get("type") or "")
    if kind == "exact":
        return _check_exact(rows, expected)
    if kind == "exact_per_key":
        return _check_exact_per_key(rows, expected)
    if kind == "trend_pattern":
        return _check_trend_pattern(rows, expected)
    if kind == "top_set":
        return _check_top_set(rows, expected)
    return None
