from typing import Any, Literal, TypedDict


class DataAgentState(TypedDict, total=False):
    run_id: str
    user_id: str
    question: str
    bypass_cache: bool
    graph_mode: Literal["chatbi", "full"]

    route: Literal["simple", "complex"]
    schema_context: str

    sql_attempts: list[dict[str, Any]]
    query_result: dict[str, Any]
    hard_guard_result: dict[str, Any]
    hard_guard_feedback: str
    execution_feedback: str
    validation_feedback: str
    dq_result: dict[str, Any]
    dq_feedback: str
    sql_retry_count: int

    approval_status: Literal["not_required", "waiting", "approved", "rejected"]
    approval_reason: str

    rag_result: dict[str, Any]
    cross_validation: str

    insight_report: dict[str, Any]
    recommendations: list[str]
    final_report: dict[str, Any]

    warnings: list[str]
    errors: list[str]
