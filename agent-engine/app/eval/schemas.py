"""golden_spec schema：与 app/graph/state.ResolvedIntent 同构（评测契约 = agent 契约）。"""
from typing import Any, Literal, TypedDict


class GoldenTimeRange(TypedDict, total=False):
    type: Literal["none", "relative", "absolute"]
    relative: dict[str, Any]
    absolute: dict[str, Any]
    granularity: str | None


class GoldenFilter(TypedDict, total=False):
    field: str
    op: str
    value: Any


class GoldenOrdering(TypedDict, total=False):
    field: str
    direction: Literal["asc", "desc"]
    limit: int


class GoldenSpec(TypedDict, total=False):
    intent: Literal["aggregate", "trend", "ranking", "detail"]
    metrics: list[str]
    dimensions: list[str]
    time_range: GoldenTimeRange
    filters: list[GoldenFilter]
    ordering: GoldenOrdering | None
