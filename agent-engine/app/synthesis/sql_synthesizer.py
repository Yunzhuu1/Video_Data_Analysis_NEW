"""确定性 SQL 合成器：从 ResolvedIntent + 指标字典生成 SQL（同意图同 SQL）。

v1 规则：
- 单指标；多指标暂不支持（抛 SynthesisError，由节点降级 raw SQL）。
- metric_daily 路径：指标表达式为列名，按分组粒度决定是否 SUM 包裹。
- ranking 或 metric_daily 无法支撑的维度（content/creator）：走明细事实表
  （fact_formula + fact_event_filter）。
- 相对时间由解析器已展开为 absolute；这里只处理 absolute。
"""
from __future__ import annotations

from typing import Any

from app.graph.state import ResolvedIntent


class SynthesisError(Exception):
    """合成器无法处理该意图（应降级到 raw SQL 生成）。"""


_ALIAS = {
    "metric_daily": "md",
    "user_behavior_fact": "ubf",
    "play_detail": "pd",
}

DIMENSIONS = [
    {"code": "date", "name": "日期", "description": "时间维度（日粒度）"},
    {"code": "category", "name": "分类", "description": "内容分类（美食/美妆/游戏）"},
    {"code": "content", "name": "内容", "description": "单个视频（content_id）"},
    {"code": "creator", "name": "创作者", "description": "创作者（creator_id）"},
]


def _field_expr(source: str, field: str) -> tuple[str, list[str]]:
    """Return (sql_expr, join_clauses) for a semantic field on a source table."""
    alias = _ALIAS.get(source, source)
    if source == "user_behavior_fact":
        if field == "date":
            return f"DATE({alias}.timestamp)", []
        if field == "category":
            return "cd.category", [f"JOIN content_dim cd ON {alias}.content_id = cd.content_id"]
        if field == "content":
            return f"{alias}.content_id", []
        if field == "creator":
            return f"{alias}.creator_id", []
        return f"{alias}.{field}", []
    if source == "play_detail":
        if field == "date":
            return f"DATE({alias}.created_at)", []
        if field == "content":
            return f"{alias}.content_id", []
        return f"{alias}.{field}", []
    # metric_daily
    return f"{alias}.{field}", []


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def _filter_cond(expr: str, flt: dict[str, Any]) -> str:
    op = str(flt.get("op") or "=").lower()
    value = flt.get("value")
    if op == "in":
        values = value if isinstance(value, list) else [value]
        return f"{expr} IN ({', '.join(_format_value(v) for v in values)})"
    if op == "between" and isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{expr} BETWEEN {_format_value(value[0])} AND {_format_value(value[1])}"
    return f"{expr} {op} {_format_value(value)}"


def _limit(ordering: dict[str, Any] | None, default: int) -> int:
    limit = (ordering or {}).get("limit")
    if not limit:
        return default
    return max(1, int(limit))


def _resolve_path(mdef: dict[str, Any], intent: str, dims: list[str]) -> dict[str, Any]:
    source = mdef.get("sourceTable") or "metric_daily"
    if intent == "ranking":
        if source == "metric_daily" and mdef.get("factFormula"):
            return {
                "source": "user_behavior_fact",
                "expr": mdef["factFormula"],
                "event_filter": mdef.get("factEventFilter"),
            }
        return {
            "source": source,
            "expr": mdef.get("formula") or "COUNT(*)",
            "event_filter": None,
        }
    # aggregate / trend
    if source == "metric_daily" and set(dims) <= {"date", "category"}:
        return {
            "source": "metric_daily",
            "expr": mdef.get("formula") or "total_plays",
            "event_filter": None,
        }
    if mdef.get("factFormula"):
        return {
            "source": "user_behavior_fact",
            "expr": mdef["factFormula"],
            "event_filter": mdef.get("factEventFilter"),
        }
    return {
        "source": source,
        "expr": mdef.get("formula") or "COUNT(*)",
        "event_filter": None,
    }


def synthesize(intent: ResolvedIntent, metric_defs: dict[str, dict[str, Any]]) -> str:
    """Deterministically synthesize SELECT SQL from a resolved intent.

    v1 规则（metric-alias 起扩展）：
    - 单指标：任意源路径（metric_daily 列 / play_detail / 事实路径）。
    - 多指标：全部指标经 _resolve_path 后落在 metric_daily 列路径 且 intent ∈ {aggregate, trend}
      才合成（单 FROM + 多 SELECT 列）；否则抛 SynthesisError（降级 raw SQL）——
      事实路径多指标各指标 factEventFilter 不同会合成空结果 WHERE（review P1）。
    """
    metrics = intent.get("metrics") or []
    if not metrics:
        raise SynthesisError("no metrics specified")
    it = intent.get("intent", "aggregate")
    dims = list(intent.get("dimensions") or [])
    filters = list(intent.get("filters") or [])
    tr = intent.get("time_range") or {"type": "none", "granularity": None}
    ordering = intent.get("ordering") or {}

    # 解析每个 metric 的合成路径（_resolve_path 会按 intent/dims 动态路由）
    paths: dict[str, dict[str, Any]] = {}
    for code in metrics:
        mdef = metric_defs.get(code)
        if mdef is None:
            raise SynthesisError(f"unknown metric code: {code}")
        paths[code] = _resolve_path(mdef, it, dims)

    multi = len(metrics) > 1
    if multi:
        # 约束校验（显式失败优于错误 SQL）：intent 限 aggregate/trend；全 metric_daily 列路径
        if it not in ("aggregate", "trend"):
            raise SynthesisError(f"multi-metric synthesis not supported for intent={it}")
        if any(paths[c]["source"] != "metric_daily" for c in metrics):
            raise SynthesisError("multi-metric synthesis only supports metric_daily path")

    first = paths[metrics[0]]
    source = first["source"]
    alias = _ALIAS.get(source, source)
    event_filter = first["event_filter"]

    # group-by set (trend always includes date on the x axis)
    gb: list[str] = []
    if it == "trend":
        gb = ["date"] + [d for d in dims if d != "date"]
    elif it in ("aggregate", "ranking"):
        gb = list(dims)

    # metric expressions（metric_daily rows are at (date, category) grain；多指标每列各自 SUM）
    agg_exprs: list[tuple[str, str]] = []
    for code in metrics:
        expr = paths[code]["expr"]
        if source == "metric_daily" and set(gb) != {"date", "category"}:
            expr = f"SUM({expr})"
        agg_exprs.append((code, expr))

    # resolve field expressions + joins
    joins: list[str] = []
    field_exprs: dict[str, str] = {}
    for f in sorted(set(gb) | ({"date"} if it == "trend" else set())):
        e, j = _field_expr(source, f)
        field_exprs[f] = e
        joins.extend(j)

    # WHERE
    conds: list[str] = []
    if event_filter:
        conds.append(event_filter)
    for flt in filters:
        fexpr, j = _field_expr(source, str(flt.get("field") or ""))
        joins.extend(j)
        conds.append(_filter_cond(fexpr, flt))
    if tr.get("type") == "absolute":
        absolute = tr.get("absolute") or {}
        start = absolute.get("start")
        end = absolute.get("end")
        if start and end:
            tcol = metric_defs[metrics[0]].get("timeField") or "date"
            time_expr, j = _field_expr(source, tcol)
            joins.extend(j)
            end_sql = str(end) + (" 23:59:59" if len(str(end)) <= 10 else "")
            conds.append(f"{time_expr} BETWEEN '{start}' AND '{end_sql}'")
    where = (" WHERE " + " AND ".join(conds)) if conds else ""

    join_sql = (" " + " ".join(dict.fromkeys(joins))) if joins else ""

    # detail intent（单指标；多指标已在约束排除）
    if it == "detail":
        return f"SELECT * FROM {source} {alias}{join_sql}{where} LIMIT {_limit(ordering, 100)}".strip()

    # SELECT columns
    select_cols: list[str] = []
    if it == "trend":
        select_cols.append(f"{field_exprs['date']} AS date")
    for f in dims:
        select_cols.append(f"{field_exprs[f]} AS {f}")
    for code, expr in agg_exprs:
        select_cols.append(f"{expr} AS {code}")

    sql = f"SELECT {', '.join(select_cols)} FROM {source} {alias}{join_sql}{where}"
    if gb:
        sql += " GROUP BY " + ", ".join(field_exprs[f] for f in gb)
    if it == "trend":
        sql += f" ORDER BY {field_exprs['date']}"
    elif it == "ranking":
        direction = str(ordering.get("direction") or "desc").upper()
        sql += f" ORDER BY {agg_exprs[0][1]} {direction} LIMIT {_limit(ordering, 10)}"
    return sql.strip()
