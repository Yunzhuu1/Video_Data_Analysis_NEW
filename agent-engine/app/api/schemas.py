from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    run_id: str = Field(alias="runId")
    user_id: str = Field(alias="userId")
    question: str
    bypass_cache: bool = Field(default=False, alias="bypassCache")
    graph_mode: Literal["chatbi"] = Field(default="chatbi", alias="graphMode")
    memory_namespace: str = Field(default="default", alias="memoryNamespace")

    model_config = {"populate_by_name": True}


class AnalyzeResponse(BaseModel):
    run_id: str = Field(alias="runId")
    status: Literal["SUCCESS", "FAILED", "WAITING_APPROVAL", "REJECTED"]
    final_report: dict[str, Any] = Field(alias="finalReport")
    warnings: list[str] = []
    approval_reason: str | None = Field(default=None, alias="approvalReason")
    resolved_intent: dict[str, Any] | None = Field(default=None, alias="resolvedIntent")
    sql_retry_count: int | None = Field(default=None, alias="sqlRetryCount")
    sql_source: str | None = Field(default=None, alias="sqlSource")
    memory_hit: bool | None = Field(default=None, alias="memoryHit")
    memory_band: str | None = Field(default=None, alias="memoryBand")
    metric_candidates: list[dict[str, Any]] | None = Field(default=None, alias="metricCandidates")
    metric_recall_mode: str | None = Field(default=None, alias="metricRecallMode")
    metric_recall_fallback: bool | None = Field(default=None, alias="metricRecallFallback")
    metric_recall_reason: str | None = Field(default=None, alias="metricRecallReason")
    metric_recall_configured_k: int | None = Field(default=None, alias="metricRecallConfiguredK")
    metric_recall_pinned_count: int | None = Field(default=None, alias="metricRecallPinnedCount")
    metric_recall_effective_k: int | None = Field(default=None, alias="metricRecallEffectiveK")
    metric_recall_full_catalog_count: int | None = Field(
        default=None, alias="metricRecallFullCatalogCount"
    )
    metric_recall_prompt_catalog_count: int | None = Field(
        default=None, alias="metricRecallPromptCatalogCount"
    )
    semantic_prompt_chars: int | None = Field(default=None, alias="semanticPromptChars")
    synthesis_error_code: str | None = Field(default=None, alias="synthesisErrorCode")
    synthesis_error_reason: str | None = Field(default=None, alias="synthesisErrorReason")
    catalog_version: str | None = Field(default=None, alias="catalogVersion")
    lineage_hash: str | None = Field(default=None, alias="lineageHash")
    metric_catalog_hash: str | None = Field(default=None, alias="metricCatalogHash")
    schema_hash: str | None = Field(default=None, alias="schemaHash")
    candidate_plans: list[dict[str, Any]] | None = Field(default=None, alias="candidatePlans")
    rejected_plans: list[dict[str, Any]] | None = Field(default=None, alias="rejectedPlans")
    selected_plan_id: str | None = Field(default=None, alias="selectedPlanId")
    plan_selection_source: str | None = Field(default=None, alias="planSelectionSource")
    planner_reason_code: str | None = Field(default=None, alias="plannerReasonCode")
    planner_skill_version: str | None = Field(default=None, alias="plannerSkillVersion")
    plan_validation: dict[str, Any] | None = Field(default=None, alias="planValidation")
    planning_retry_count: int | None = Field(default=None, alias="planningRetryCount")
    lineage_edge_ids: list[str] | None = Field(default=None, alias="lineageEdgeIds")
    legacy_planner_fallback: bool | None = Field(default=None, alias="legacyPlannerFallback")
    planner_prompt_chars: int | None = Field(default=None, alias="plannerPromptChars")
    planner_latency_ms: float | None = Field(default=None, alias="plannerLatencyMs")

    model_config = {"populate_by_name": True}


class ApprovalRequest(BaseModel):
    approved: bool


class MemoryHealth(BaseModel):
    enabled: bool
    backend: str
    status: Literal["READY", "DISABLED", "DEGRADED"]
    reason_code: str | None = Field(default=None, alias="reasonCode")

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: Literal["UP"]
    service: str
    memory: MemoryHealth
