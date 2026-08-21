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
    "creator_revenue": "cr",
    "video_revenue": "vr",
    "user_retention": "ur",
    "content_dim": "cd",
    "creator_dim": "ctd",
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
        if field == "category":
            return "cd.category", [f"JOIN content_dim cd ON {alias}.content_id = cd.content_id"]
        return f"{alias}.{field}", []
    if source == "creator_revenue":
        if field == "date":
            return f"{alias}.stat_date", []
        if field == "creator":
            return f"{alias}.creator_id", []
        return f"{alias}.{field}", []
    if source == "video_revenue":
        if field == "date":
            return f"{alias}.stat_date", []
        if field == "content":
            return f"{alias}.content_id", []
        return f"{alias}.{field}", []
    if source == "user_retention":
        if field == "date":
            return f"{alias}.stat_date", []
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


def _synthesize_join_multi(intent: dict[str, Any], metric_defs: dict[str, dict[str, Any]],
                             paths: dict[str, dict[str, Any]]) -> str:
    """冲突多指标子查询 JOIN（P2-1 统一解：来源冲突或 eventFilter 冲突）。

    - 每个指标独立子查询：SELECT <维度键expr> AS dim, <agg> AS code FROM source WHERE 各自 event_filter + 共享过滤/时间 GROUP BY 维度键
    - 外层：SELECT a.dim, a.c1, b.c2 FROM (sub1) a JOIN (sub2) b ON a.dim = b.dim
    - 维度键 expr 各子查询可用各自表表达式（cd.category vs md.category），JOIN 靠外层别名对齐（P3 语义一致即可）
    """
    it = intent.get("intent", "aggregate")
    dims = list(intent.get("dimensions") or [])
    filters = list(intent.get("filters") or [])
    tr = intent.get("time_range") or {"type": "none", "granularity": None}
    ordering = intent.get("ordering") or {}
    metrics = list(intent.get("metrics") or [])

    gb: list[str] = []
    if it == "trend":
        gb = ["date"] + [d for d in dims if d != "date"]
    elif it in ("aggregate", "ranking"):
        gb = list(dims)

    subs: list[str] = []
    aliases: list[str] = []
    for i, code in enumerate(metrics):
        path = paths[code]
        source = path["source"]
        alias = _ALIAS.get(source, source)
        alias_letter = chr(ord("a") + i)
        # 维度键表达式（该表）
        dim_exprs: list[str] = []
        field_exprs: dict[str, str] = {}
        joins: list[str] = []
        for f in sorted(set(gb) | ({"date"} if it == "trend" else set())):
            e, j = _field_expr(source, f)
            field_exprs[f] = e
            dim_exprs.append(f"{e} AS {f}")
            joins.extend(j)
        # WHERE：该指标 event_filter + 共享过滤 + 时间
        conds: list[str] = []
        if path.get("event_filter"):
            conds.append(path["event_filter"])
        for flt in filters:
            f = str(flt.get("field") or "")
            if f in metric_defs:
                continue  # 指标过滤 MVP 不做（组合降级已在入口拦截）
            fexpr, j = _field_expr(source, f)
            joins.extend(j)
            conds.append(_filter_cond(fexpr, flt))
        if tr.get("type") == "absolute":
            absolute = tr.get("absolute") or {}
            start = absolute.get("start")
            end = absolute.get("end")
            if start and end:
                tcol = metric_defs[code].get("timeField") or "date"
                time_expr, j = _field_expr(source, tcol)
                joins.extend(j)
                end_sql = str(end) + (" 23:59:59" if len(str(end)) <= 10 else "")
                conds.append(f"{time_expr} BETWEEN '{start}' AND '{end_sql}'")
        where = (" WHERE " + " AND ".join(conds)) if conds else ""
        join_sql = (" " + " ".join(dict.fromkeys(joins))) if joins else ""
        group_sql = (" GROUP BY " + ", ".join(field_exprs[f] for f in gb)) if gb else ""
        agg_expr = paths[code]["expr"]
        subs.append(f"SELECT {', '.join(dim_exprs)}, {agg_expr} AS {code} FROM {source} {alias}{join_sql}{where}{group_sql}")
        aliases.append(alias_letter)

    # 外层
    join_keys = sorted(set(gb) | ({"date"} if it == "trend" else set()))
    outer_dims = ", ".join(f"{aliases[0]}.{f}" for f in join_keys)
    outer_metrics = ", ".join(f"{aliases[i]}.{code}" for i, code in enumerate(metrics))
    joins_sql = " JOIN ".join(
        f"({subs[i]}) {aliases[i]} ON " + " AND ".join(
            f"{aliases[0]}.{key} = {aliases[i]}.{key}" for key in join_keys
        )
        for i in range(1, len(subs))
    )
    sql = f"SELECT {outer_dims}, {outer_metrics} FROM ({subs[0]}) {aliases[0]}"
    if joins_sql:
        sql += " JOIN " + joins_sql
    if it == "trend":
        sql += f" ORDER BY {aliases[0]}.date"
    elif it == "ranking":
        direction = str(ordering.get("direction") or "desc").upper()
        sql += f" ORDER BY {aliases[0]}.{metrics[0]} {direction} LIMIT {_limit(ordering, 10)}"
    return sql.strip()


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
        if it not in ("aggregate", "trend"):
            raise SynthesisError(f"multi-metric synthesis not supported for intent={it}")
        sources = {paths[c]["source"] for c in metrics}
        event_filters = {str(paths[c].get("event_filter") or "") for c in metrics}
        conflict = len(sources) > 1 or len(event_filters) > 1
        if conflict:
            # 组合降级（P2-2）：冲突多指标 + 指标值过滤 MVP 不做
            for flt in intent.get("filters") or []:
                if str(flt.get("field") or "") in metric_defs:
                    raise SynthesisError("conflict multi-metric + metric-value filter not supported")
            # JOIN 需要维度键：无 dims 且非 trend → 无法对齐（降级）
            key_set = set(dims) | ({"date"} if it == "trend" else set())
            if not key_set:
                raise SynthesisError("conflict multi-metric requires dimension keys for JOIN")
            # 统一解（P2-1）：跨源 或 eventFilter 冲突 → 子查询 JOIN
            return _synthesize_join_multi(intent, metric_defs, paths)
        # 同源同 filter：单 FROM 多列（metric_daily 验证过）
        if any(paths[c]["source"] != "metric_daily" for c in metrics):
            raise SynthesisError("same-source multi-metric only supports metric_daily path")

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

    # 指标值过滤（P2-1）：field 是指标 code → HAVING（聚合后过滤）；维度 → WHERE
    agg_map = {code: expr for code, expr in agg_exprs}
    having_conds: list[str] = []
    where_filters: list[dict[str, Any]] = []
    for flt in filters:
        f = str(flt.get("field") or "")
        if f in agg_map:
            if it not in ("aggregate", "trend"):
                raise SynthesisError(f"metric-value filter not supported for intent={it}")
            op = flt.get("op") or "="
            having_conds.append(f"{agg_map[f]} {op!s} {_format_value(flt.get('value'))}")
        else:
            where_filters.append(flt)

    # WHERE
    conds: list[str] = []
    if event_filter:
        conds.append(event_filter)
    for flt in where_filters:
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

    having = (" HAVING " + " AND ".join(having_conds)) if having_conds else ""
    sql = f"SELECT {', '.join(select_cols)} FROM {source} {alias}{join_sql}{where}"
    if gb:
        sql += " GROUP BY " + ", ".join(field_exprs[f] for f in gb)
    if having:
        sql += having
    if it == "trend":
        sql += f" ORDER BY {field_exprs['date']}"
    elif it == "ranking":
        direction = str(ordering.get("direction") or "desc").upper()
        sql += f" ORDER BY {agg_exprs[0][1]} {direction} LIMIT {_limit(ordering, 10)}"
    return sql.strip()


def synthesize_plan(intent: ResolvedIntent, snapshot: dict[str, Any], plan: dict[str, Any]) -> str:
    """只按 validated plan + run 冻结 snapshot 编译单指标 SQL；不做路径推导。"""
    metrics = list(intent.get("metrics") or [])
    if len(metrics) != 1:
        raise SynthesisError("lineage plan compiler only supports one metric")
    code = metrics[0]
    definitions = {item["metricCode"]: item for item in snapshot["metricDefinitions"]}
    paths = {item["pathId"]: item for item in snapshot["lineage"]["metricPaths"]}
    bindings = {item["bindingId"]: item for item in snapshot["lineage"]["dimensionBindings"]}
    edges = {item["edgeId"]: item for item in snapshot["lineage"]["joinEdges"]}
    mdef = definitions.get(code)
    path = paths.get(plan.get("metricPathId"))
    if mdef is None or path is None or path["metricCode"] != code:
        raise SynthesisError("plan metric/path mismatch")
    source = path["sourceTable"]
    alias = _ALIAS[source]
    routes = plan.get("fieldRoutes") or []
    route_by_usage: dict[tuple[str, str], dict[str, Any]] = {}
    edge_ids: list[str] = []
    for route in routes:
        for usage in route.get("usages") or []:
            route_by_usage[(route["semanticField"], usage)] = route
        edge_ids.extend(route.get("edgeIds") or [])

    joined: list[str] = []
    current_tables = {source}
    for edge_id in dict.fromkeys(edge_ids):
        edge = edges.get(edge_id)
        if edge is None or edge["fromTable"] not in current_tables:
            raise SynthesisError("plan contains non-forward edge")
        left = _ALIAS[edge["fromTable"]]
        right = _ALIAS[edge["toTable"]]
        on = " AND ".join(
            f"{left}.{a} = {right}.{b}"
            for a, b in zip(edge["fromColumns"], edge["toColumns"])
        )
        joined.append(f"JOIN {edge['toTable']} {right} ON {on}")
        current_tables.add(edge["toTable"])

    def field_expr(field: str, usage: str) -> str:
        route = route_by_usage.get((field, usage))
        if route is None:
            raise SynthesisError(f"missing selected field route: {field}/{usage}")
        if route["routeKind"] == "TIME_FIELD":
            raw = f"{alias}.{path['timeFieldRef']}"
            return f"DATE({raw})" if usage == "TIME_BUCKET" and path["timeFieldRef"] not in {"date", "stat_date"} else raw
        binding = bindings.get(route.get("bindingId"))
        if binding is None:
            raise SynthesisError(f"unknown binding: {route.get('bindingId')}")
        return f"{_ALIAS[binding['tableName']]}.{binding['labelColumn']}"

    expression = mdef.get("factFormula") if path["expressionRef"] == "fact" else mdef.get("formula")
    if not expression:
        raise SynthesisError("missing metric expression")
    dims = list(intent.get("dimensions") or [])
    it = intent.get("intent", "aggregate")
    gb = (["date"] + [d for d in dims if d != "date"]) if it == "trend" else dims
    if source == "metric_daily" and set(gb) != {"date", "category"}:
        expression = f"SUM({expression})"
    select_cols = []
    group_exprs = []
    if it == "trend":
        date_expr = field_expr("date", "TIME_BUCKET")
        select_cols.append(f"{date_expr} AS date")
        group_exprs.append(date_expr)
    for dim in dims:
        expr = field_expr(dim, "GROUP_BY")
        select_cols.append(f"{expr} AS {dim}")
        group_exprs.append(expr)
    select_cols.append(f"{expression} AS {code}")
    conditions = []
    if path.get("eventFilterRef") == "fact" and mdef.get("factEventFilter"):
        conditions.append(str(mdef["factEventFilter"]))
    having = []
    for flt in intent.get("filters") or []:
        field = str(flt.get("field") or "")
        if field == code:
            having.append(_filter_cond(expression, flt))
        else:
            conditions.append(_filter_cond(field_expr(field, "FILTER"), flt))
    tr = intent.get("time_range") or {}
    if tr.get("type") == "absolute":
        absolute = tr.get("absolute") or {}
        if absolute.get("start") and absolute.get("end"):
            time_expr = field_expr("date", "TIME_FILTER")
            end = str(absolute["end"])
            if len(end) <= 10:
                end += " 23:59:59"
            conditions.append(f"{time_expr} BETWEEN '{absolute['start']}' AND '{end}'")
    sql = f"SELECT {', '.join(select_cols)} FROM {source} {alias}"
    if joined:
        sql += " " + " ".join(joined)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    if group_exprs:
        sql += " GROUP BY " + ", ".join(group_exprs)
    if having:
        sql += " HAVING " + " AND ".join(having)
    ordering = intent.get("ordering") or {}
    if it == "trend":
        sql += " ORDER BY date"
    elif it == "ranking":
        direction = str(ordering.get("direction") or "desc").upper()
        sql += f" ORDER BY {expression} {direction} LIMIT {_limit(ordering, 10)}"
    return sql
