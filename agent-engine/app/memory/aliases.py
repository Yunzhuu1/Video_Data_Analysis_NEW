"""AliasStore：指标表达别名（aliases.yaml → 词组级 alias → metric_code）。

- 最长匹配优先（「播放走势」先于「播放」）；catalog 精确名优先级更高（不在此重复）。
- 单例惰性加载；测试可 reset。
"""
from __future__ import annotations

import json
from pathlib import Path

_ALIASES_PATH = Path(__file__).resolve().parents[1] / "eval" / "aliases.yaml"
_cache: dict[str, str] | None = None


def load_aliases() -> dict[str, str]:
    """alias → metric_code（长词在前，最长匹配优先）。"""
    data = json.loads(_ALIASES_PATH.read_text(encoding="utf-8"))
    items = [(str(x["alias"]), str(x["metric_code"])) for x in data.get("aliases", [])]
    items.sort(key=lambda kv: len(kv[0]), reverse=True)
    return dict(items)


def get_aliases() -> dict[str, str]:
    global _cache
    if _cache is None:
        _cache = load_aliases()
    return _cache


def reset_aliases() -> None:
    global _cache
    _cache = None
