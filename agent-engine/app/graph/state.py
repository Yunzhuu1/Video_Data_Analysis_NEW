from typing import Any, Literal, TypedDict


class TimeRange(TypedDict, total=False):
    type: Literal["none", "relative", "absolute"]
    relative: dict[str, Any]
    absolute: dict[str, Any]
    granularity: str | None


FilterOp = Literal["=", "in", "between", ">", ">=", "<", "<="]


class ResolvedFilter(TypedDict, total=False):
    field: str
    op: FilterOp
    value: Any


class ResolvedIntent(TypedDict, total=False):
    """LLM 语义解析的契约，与 agent-eval-harness 的 golden_spec 同构。"""
    intent: Literal["aggregate", "trend", "ranking", "detail"]
    metrics: list[str]
    dimensions: list[str]
    time_range: TimeRange
    filters: list[ResolvedFilter]  # field 为指标 code 时 op 比较（HAVING）
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

    metric_candidates: list[dict[str, Any]]
    metric_recall_mode: Literal["topk", "full", "full_fallback"]
    metric_recall_fallback: bool
    metric_recall_reason: str | None
    metric_recall_top_k: int
    metric_recall_pinned_count: int
    metric_recall_effective_k: int
    metric_recall_full_catalog_count: int
    metric_recall_prompt_catalog_count: int
    semantic_prompt_chars: int | None
    synthesis_error_code: str | None
    synthesis_error_reason: str | None

    lineage_snapshot: dict[str, Any]
    catalog_version: str
    lineage_hash: str
    metric_catalog_hash: str
    schema_hash: str
    candidate_plans: list[dict[str, Any]]
    rejected_plans: list[dict[str, Any]]
    selected_plan_id: str | None
    plan_selection_source: str
    planner_reason_code: str | None
    planner_skill_version: str | None
    plan_validation: dict[str, Any]
    validated_snapshot_fingerprint: str
    planning_retry_count: int
    lineage_edge_ids: list[str]
    legacy_planner_fallback: bool
    planner_prompt_chars: int
    planner_latency_ms: float

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
