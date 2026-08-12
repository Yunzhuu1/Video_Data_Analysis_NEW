"""确定性比较器：golden_spec vs agent ResolvedIntent，输出四层评分。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.eval.normalizers import (
    expand_time_range,
    normalize_dimension,
    normalize_filter,
    normalize_metric,
)

FIELD_NAMES = ["intent", "metrics", "dimensions", "time_range", "filters", "ordering"]


@dataclass
class SpecScore:
    matched: bool
    core_ok: bool
    field_hits: int
    field_total: int
    fields: dict[str, bool] = field(default_factory=dict)


def _time_ok(actual: dict[str, Any] | None, golden: dict[str, Any] | None, eval_date: str) -> bool:
    g = expand_time_range(golden, eval_date)
    a = expand_time_range(actual, eval_date)
    if g is None and a is None:
        return True
    if g is None or a is None:
        return False
    g_start, g_end, g_gran = g
    a_start, a_end, a_gran = a
    if g_gran and a_gran and g_gran != a_gran:
        return False
    if g_end != a_end:
        return False
    g_days = (date.fromisoformat(g_end) - date.fromisoformat(g_start)).days
    a_days = (date.fromisoformat(a_end) - date.fromisoformat(a_start)).days
    return abs(g_days - a_days) <= 1


def _ordering_ok(actual: dict[str, Any] | None, golden: dict[str, Any] | None) -> bool:
    if golden is None:
        return actual is None
    if actual is None:
        return False
    return (
        normalize_metric(actual.get("field")) == normalize_metric(golden.get("field"))
        and str(actual.get("direction") or "desc").lower() == str(golden.get("direction") or "desc").lower()
        and int(actual.get("limit") or 0) == int(golden.get("limit") or 0)
    )


def _unresolved_score(golden: dict[str, Any]) -> SpecScore:
    return SpecScore(
        matched=False,
        core_ok=False,
        field_hits=0,
        field_total=len(FIELD_NAMES),
        fields={name: False for name in FIELD_NAMES},
    )


def compare_spec(
    actual: dict[str, Any] | None,
    golden: dict[str, Any] | None,
    eval_date: str = "2023-10-14",
) -> SpecScore | None:
    """Compare agent ResolvedIntent (actual) against golden_spec.

    Returns None for open cases (no golden_spec).
    """
    if golden is None:
        return None
    if not actual:
        return _unresolved_score(golden)

    fields: dict[str, bool] = {}
    fields["intent"] = str(actual.get("intent")) == str(golden.get("intent"))

    g_metrics = {normalize_metric(m) for m in (golden.get("metrics") or [])}
    a_metrics = {normalize_metric(m) for m in (actual.get("metrics") or [])}
    fields["metrics"] = bool(g_metrics) and a_metrics == g_metrics

    g_dims = {normalize_dimension(d) for d in (golden.get("dimensions") or [])}
    a_dims = {normalize_dimension(d) for d in (actual.get("dimensions") or [])}
    fields["dimensions"] = a_dims == g_dims

    fields["time_range"] = _time_ok(actual.get("time_range"), golden.get("time_range"), eval_date)

    g_filters = {normalize_filter(f) for f in (golden.get("filters") or [])}
    a_filters = {normalize_filter(f) for f in (actual.get("filters") or [])}
    fields["filters"] = g_filters == a_filters

    fields["ordering"] = _ordering_ok(actual.get("ordering"), golden.get("ordering"))

    hits = sum(1 for ok in fields.values() if ok)
    return SpecScore(
        matched=hits == len(fields),
        core_ok=fields["metrics"],
        field_hits=hits,
        field_total=len(fields),
        fields=fields,
    )


def aggregate_scores(scores: list[SpecScore | None]) -> dict[str, float]:
    """四层评分聚合：L1 核心口径 / L2 严格全字段 / L3 平均字段匹配 / L4 分项。"""
    judged = [s for s in scores if s is not None]
    total = len(judged)
    if total == 0:
        return {"core": 0.0, "strict": 0.0, "avg_field": 0.0, "intent": 0.0, "metrics": 0.0,
                "dimensions": 0.0, "time_range": 0.0, "filters": 0.0, "ordering": 0.0}
    core = sum(1 for s in judged if s.core_ok) / total
    strict = sum(1 for s in judged if s.matched) / total
    avg_field = sum(s.field_hits for s in judged) / sum(s.field_total for s in judged)
    per_field = {name: sum(1 for s in judged if s.fields.get(name)) / total for name in FIELD_NAMES}
    result = {"core": core, "strict": strict, "avg_field": avg_field}
    result.update(per_field)
    return result
