from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_RESOURCE = _ROOT / "src/main/resources"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMPONENTS = ("lineage", "metric", "schema", "catalog")


@dataclass(frozen=True)
class SnapshotIntegrityResult:
    valid: bool
    snapshot_fingerprint: str | None
    mismatched_components: tuple[str, ...]
    declared_hashes: dict[str, str | None]
    actual_hashes: dict[str, str | None]
    reason: str | None = None


class SnapshotIntegrityError(ValueError):
    def __init__(self, result: SnapshotIntegrityResult):
        self.result = result
        components = ",".join(result.mismatched_components) or "unknown"
        super().__init__(f"snapshot integrity mismatch: {components}")


def canonical_bytes(value: Any) -> bytes:
    """项目受限 canonical JSON：UTF-8、code-point key 排序、紧凑编码。"""
    _validate_numbers(value)
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def snapshot_hashes(snapshot: Mapping[str, Any]) -> dict[str, str]:
    """Recompute all hashes from the supplied in-memory payload."""
    lineage = snapshot["lineage"]
    metrics = snapshot["metricDefinitions"]
    schema = snapshot["schemaProjection"]
    hashes = {
        "lineage": canonical_hash(lineage),
        "metric": canonical_hash(metrics),
        "schema": canonical_hash(schema),
        "catalog": canonical_hash({"lineage": lineage, "metrics": metrics, "schema": schema}),
    }
    fingerprint_payload = {
        "catalogVersion": snapshot.get("catalogVersion"),
        "lineageHash": snapshot.get("lineageHash"),
        "metricCatalogHash": snapshot.get("metricCatalogHash"),
        "schemaHash": snapshot.get("schemaHash"),
        "lineage": lineage,
        "metricDefinitions": metrics,
        "schemaProjection": schema,
    }
    hashes["fingerprint"] = canonical_hash(fingerprint_payload)
    return hashes


def refresh_snapshot_declarations(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Test/fixture helper for creating a new self-consistent snapshot version."""
    computed = snapshot_hashes(snapshot)
    snapshot.update({
        "lineageHash": computed["lineage"],
        "metricCatalogHash": computed["metric"],
        "schemaHash": computed["schema"],
        "catalogVersion": computed["catalog"],
    })
    return snapshot


def inspect_snapshot_integrity(snapshot: Mapping[str, Any]) -> SnapshotIntegrityResult:
    declared = {
        "lineage": snapshot.get("lineageHash"),
        "metric": snapshot.get("metricCatalogHash"),
        "schema": snapshot.get("schemaHash"),
        "catalog": snapshot.get("catalogVersion"),
    }
    actual: dict[str, str | None] = {component: None for component in _COMPONENTS}
    fingerprint = None
    reason = None
    try:
        computed = snapshot_hashes(snapshot)
        actual.update({component: computed[component] for component in _COMPONENTS})
        fingerprint = computed["fingerprint"]
    except (KeyError, TypeError, ValueError) as exc:
        reason = str(exc)
    mismatched = []
    for component in _COMPONENTS:
        value = declared[component]
        if not isinstance(value, str) or not _HASH_PATTERN.fullmatch(value) or actual[component] != value:
            mismatched.append(component)
    if reason and not mismatched:
        mismatched.extend(_COMPONENTS)
    return SnapshotIntegrityResult(
        valid=not mismatched and reason is None,
        snapshot_fingerprint=fingerprint,
        mismatched_components=tuple(mismatched),
        declared_hashes=declared,
        actual_hashes=actual,
        reason=reason,
    )


def require_snapshot_integrity(snapshot: Mapping[str, Any]) -> SnapshotIntegrityResult:
    result = inspect_snapshot_integrity(snapshot)
    if not result.valid:
        raise SnapshotIntegrityError(result)
    return result


def seal_compilation_snapshot(
    snapshot: Mapping[str, Any], *, validated_fingerprint: str, plan_fingerprint: str,
) -> Mapping[str, Any]:
    """Copy, validate and recursively freeze the exact compiler input."""
    try:
        private_copy = json.loads(canonical_bytes(dict(snapshot)))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        result = SnapshotIntegrityResult(
            False, None, ("catalog",), {}, {}, reason=str(exc),
        )
        raise SnapshotIntegrityError(result) from exc
    integrity = require_snapshot_integrity(private_copy)
    actual = integrity.snapshot_fingerprint
    if actual != validated_fingerprint or actual != plan_fingerprint:
        result = SnapshotIntegrityResult(
            False,
            actual,
            ("validatedFingerprint",),
            {"validatedFingerprint": validated_fingerprint, "planFingerprint": plan_fingerprint},
            {"validatedFingerprint": actual, "planFingerprint": actual},
            reason="compiler snapshot differs from the validator-approved snapshot",
        )
        raise SnapshotIntegrityError(result)
    return _freeze_json(private_copy)


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


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
