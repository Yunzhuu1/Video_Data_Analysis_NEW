"""运行时指标别名注册表：memory / metric recall / eval 共用一个数据源。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_ALIASES_PATH = Path(__file__).resolve().parents[1] / "resources" / "metric_aliases.yaml"


@dataclass(frozen=True)
class AliasRecord:
    alias: str
    metric_code: str
    covered_by: tuple[str, ...]


@dataclass(frozen=True)
class AliasBundle:
    """同一次解析产生运行时 map 与评测 records，避免两套 loader 漂移。"""

    alias_map: dict[str, str]
    alias_records: list[AliasRecord]


_cache: AliasBundle | None = None


def load_alias_bundle(path: Path | None = None) -> AliasBundle:
    source = path or _ALIASES_PATH
    data = json.loads(source.read_text(encoding="utf-8"))
    raw_records = data.get("aliases")
    if not isinstance(raw_records, list):
        raise TypeError("alias resource must contain an aliases list")

    records: list[AliasRecord] = []
    ownership: dict[str, str] = {}
    for raw in raw_records:
        alias = str(raw.get("alias") or "").strip()
        metric_code = str(raw.get("metric_code") or "").strip()
        covered_by = tuple(str(x) for x in (raw.get("covered_by") or []))
        if not alias or not metric_code:
            raise ValueError("alias and metric_code must be non-empty")
        previous = ownership.get(alias)
        if previous is not None and previous != metric_code:
            raise ValueError(f"conflicting alias mapping: {alias} -> {previous}/{metric_code}")
        if previous is not None:
            raise ValueError(f"duplicate alias: {alias}")
        ownership[alias] = metric_code
        records.append(AliasRecord(alias, metric_code, covered_by))

    ordered = sorted(records, key=lambda x: (-len(x.alias), x.alias, x.metric_code))
    return AliasBundle(
        alias_map={record.alias: record.metric_code for record in ordered},
        alias_records=records,
    )


def load_aliases(path: Path | None = None) -> dict[str, str]:
    """兼容旧调用：返回 alias -> metric_code 映射。"""
    return load_alias_bundle(path).alias_map


def get_alias_bundle() -> AliasBundle:
    global _cache
    if _cache is None:
        _cache = load_alias_bundle()
    return _cache


def get_aliases() -> dict[str, str]:
    return get_alias_bundle().alias_map


def reset_aliases() -> None:
    global _cache
    _cache = None
