from typing import Any, Literal, TypedDict


class TimeRange(TypedDict, total=False):
    type: Literal["none", "relative", "absolute"]
    relative: dict[str, Any]
    absolute: dict[str, Any]
    granularity: str | None


class ResolvedIntent(TypedDict, total=False):
    """LLM 语义解析的契约，与 agent-eval-harness 的 golden_spec 同构。"""
    intent: Literal["aggregate", "trend", "ranking", "detail"]
    metrics: list[str]
    dimensions: list[str]
    time_range: TimeRange
    filters: list[dict[str, Any]]
    ordering: dict[str, Any] | None
    confidence: float
    coverage: str


class DataAgentState(TypedDict, total=False):
    run_id: str
    user_id: str
    question: str
    bypass_cache: bool
    graph_mode: Literal["chatbi"]

    route: Literal["simple", "complex"]
    schema_context: str

    resolved_intent: ResolvedIntent
    semantic_ok: bool
    sql_source: Literal["semantic", "fallback", "memory"]
    memory_hit: bool
    memory_band: Literal["hit", "inject", "hit_rejected"]
    memory_namespace: str

    sql_attempts: list[dict[str, Any]]
    query_result: dict[str, Any]
    hard_guard_result: dict[str, Any]
    hard_guard_feedback: str
    execution_feedback: str
    dq_result: dict[str, Any]
    dq_feedback: str
    sql_retry_count: int

    approval_status: Literal["not_required", "waiting", "approved", "rejected"]
    approval_reason: str

    final_report: dict[str, Any]

    warnings: list[str]
    errors: list[str]
