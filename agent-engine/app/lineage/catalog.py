from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_RESOURCE = _ROOT / "src/main/resources"


def canonical_bytes(value: Any) -> bytes:
    """项目受限 canonical JSON：UTF-8、code-point key 排序、紧凑编码。"""
    _validate_numbers(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _validate_numbers(value: Any) -> None:
    if isinstance(value, float):
        raise TypeError("canonical JSON does not allow floating point numbers")
    if (isinstance(value, int) and not isinstance(value, bool)
            and not -(2**63) <= value <= 2**63 - 1):
        raise ValueError("canonical JSON integer outside signed 64-bit range")
    if isinstance(value, dict):
        for item in value.values():
            _validate_numbers(item)
    elif isinstance(value, list):
        for item in value:
            _validate_numbers(item)


def _metric_definitions() -> list[dict[str, Any]]:
    raw = json.loads((_RESOURCE / "metric_catalog.json").read_text(encoding="utf-8"))
    normalized = [{
        "metricCode": item.get("metricCode"),
        "formula": item.get("formula"),
        "dimensions": sorted(item.get("dimensions") or []),
        "sourceTable": item.get("sourceTable"),
        "timeField": item.get("timeField"),
        "factFormula": item.get("factFormula"),
        "factEventFilter": item.get("factEventFilter"),
    } for item in raw]
    return sorted(normalized, key=lambda item: item["metricCode"])


def _schema_projection(lineage: dict[str, Any]) -> dict[str, list[str]]:
    sql = (_RESOURCE / "schema.sql").read_text(encoding="utf-8")
    tables: dict[str, list[str]] = {}
    header = re.compile(
        r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?(\w+)`?\s*\(", re.IGNORECASE,
    )
    for match in header.finditer(sql):
        start = match.end() - 1
        depth = 0
        quoted = False
        end = None
        index = start
        while index < len(sql):
            char = sql[index]
            if char == "'":
                if quoted and index + 1 < len(sql) and sql[index + 1] == "'":
                    index += 2
                    continue
                quoted = not quoted
            elif not quoted and char == "(":
                depth += 1
            elif not quoted and char == ")":
                depth -= 1
                if depth == 0:
                    end = index
                    break
            index += 1
        if end is None:
            raise ValueError(f"unclosed CREATE TABLE {match.group(1)}")
        columns = []
        for line in sql[start + 1:end].splitlines():
            line = line.strip().rstrip(",")
            found = re.match(r"`?(\w+)`?\s+(?:BIGINT|INT|TINYINT|VARCHAR|CHAR|TEXT|DECIMAL|DATE|DATETIME|TIMESTAMP|JSON|DOUBLE|FLOAT)", line, re.IGNORECASE)
            if found:
                columns.append(found.group(1).lower())
        tables[match.group(1).lower()] = sorted(columns)
    wanted = sorted(item["tableName"] for item in lineage["tables"])
    return {table: tables[table] for table in wanted}


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    lineage = snapshot["lineage"]
    schema = snapshot["schemaProjection"]
    metrics = {item["metricCode"] for item in snapshot["metricDefinitions"]}
    for collection, key in (("tables", "tableName"), ("metricPaths", "pathId"),
                            ("dimensionBindings", "bindingId"), ("joinEdges", "edgeId")):
        ids = [item[key] for item in lineage[collection]]
        if len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"duplicate/empty {key}")
    for path in lineage["metricPaths"]:
        _require_column(schema, path["sourceTable"], path["timeFieldRef"])
        if path["metricCode"] not in metrics:
            raise ValueError(f"unknown metricCode in path {path['pathId']}")
    for binding in lineage["dimensionBindings"]:
        _require_column(schema, binding["tableName"], binding["keyColumn"])
        _require_column(schema, binding["tableName"], binding["labelColumn"])
    for edge in lineage["joinEdges"]:
        if edge["cardinalityFromTo"] not in {"N:1", "1:1"}:
            raise ValueError(f"unsafe edge {edge['edgeId']}")
        if len(edge["fromColumns"]) != len(edge["toColumns"]):
            raise ValueError(f"join column count mismatch {edge['edgeId']}")
        for column in edge["fromColumns"]:
            _require_column(schema, edge["fromTable"], column)
        for column in edge["toColumns"]:
            _require_column(schema, edge["toTable"], column)


def _require_column(schema: dict[str, list[str]], table: str, column: str) -> None:
    if table not in schema or column.lower() not in schema[table]:
        raise ValueError(f"unknown physical field {table}.{column}")


def load_mock_snapshot() -> dict[str, Any]:
    lineage = json.loads((_RESOURCE / "lineage_catalog.json").read_text(encoding="utf-8"))
    metrics = _metric_definitions()
    schema = _schema_projection(lineage)
    combined = {"lineage": lineage, "metrics": metrics, "schema": schema}
    snapshot = {
        "catalogVersion": canonical_hash(combined),
        "lineageHash": canonical_hash(lineage),
        "metricCatalogHash": canonical_hash(metrics),
        "schemaHash": canonical_hash(schema),
        "lineage": lineage,
        "metricDefinitions": metrics,
        "schemaProjection": schema,
    }
    validate_snapshot(snapshot)
    return snapshot
