from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.schemas import AnalyzeRequest, AnalyzeResponse, ApprovalRequest, HealthResponse
from app.graph import nodes
from app.graph.graph_builder import resume_graph, run_chatbi_graph
from app.memory.retriever import normalize_question
from app.settings import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="UP", service=settings.service_name)


# ---------------------------------------------------------------------------
# 记忆控制 API（内部，仅评测验证/调试用，不参与运行时读路径）
# ---------------------------------------------------------------------------
class MemorySeedRequest(BaseModel):
    namespace: str = Field(default="default")
    question: str
    intent: dict
    metric_codes: list[str] = []


class MemoryClearRequest(BaseModel):
    namespace: str = "default"


def _check_internal_token(x_internal_token: str | None) -> None:
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(status_code=403, detail="invalid internal token")


@router.post("/internal/memory/seed")
async def memory_seed(req: MemorySeedRequest, x_internal_token: str | None = Header(default=None)) -> dict:
    """预置记忆条目。拒绝 default namespace（生产记忆仅由写钩子沉淀，防毒化）。"""
    _check_internal_token(x_internal_token)
    if req.namespace == "default":
        raise HTTPException(status_code=400, detail="seed into default namespace is forbidden")
    if not req.intent or not req.intent.get("metrics"):
        raise HTTPException(status_code=400, detail="intent must contain metrics")
    if nodes.memory is None:
        raise HTTPException(status_code=503, detail="memory not initialized")
    from app.memory.store import compute_resolver_hash
    entry_id = await nodes.memory.upsert(
        normalize_question(req.question), req.intent, req.metric_codes,
        compute_resolver_hash(), namespace=req.namespace)
    return {"entryId": entry_id, "namespace": req.namespace}


@router.post("/internal/memory/clear")
async def memory_clear(req: MemoryClearRequest, x_internal_token: str | None = Header(default=None)) -> dict:
    """清空某 namespace（幂等：不存在也返回成功）。"""
    _check_internal_token(x_internal_token)
    if nodes.memory is None:
        raise HTTPException(status_code=503, detail="memory not initialized")
    await nodes.memory.clear(req.namespace)
    return {"cleared": req.namespace}


@router.get("/internal/memory/entries")
async def memory_entries(namespace: str = "default",
                         x_internal_token: str | None = Header(default=None)) -> dict:
    """查看某 namespace 条目（仅评测验证/调试）。"""
    _check_internal_token(x_internal_token)
    if nodes.memory is None:
        raise HTTPException(status_code=503, detail="memory not initialized")
    entries = await nodes.memory.all(namespace)
    return {"namespace": namespace, "count": len(entries),
            "entries": [{"id": e.id, "norm_question": e.norm_question,
                         "metric_codes": e.metric_codes, "hit_count": e.hit_count}
                        for e in entries]}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    state = await run_chatbi_graph(
        {
            "run_id": request.run_id,
            "user_id": request.user_id,
            "question": request.question,
            "bypass_cache": request.bypass_cache,
            "graph_mode": "chatbi",
            "memory_namespace": request.memory_namespace,
            "warnings": [],
            "errors": [],
        }
    )
    status = "SUCCESS" if state.get("final_report") else "FAILED"
    if state.get("approval_status") == "waiting":
        status = "WAITING_APPROVAL"
    return AnalyzeResponse(
        runId=state["run_id"],
        status=status,
        finalReport=state.get("final_report") or {},
        warnings=state.get("warnings", []),
        approvalReason=state.get("approval_reason"),
        resolvedIntent=state.get("resolved_intent"),
        sqlRetryCount=state.get("sql_retry_count"),
        sqlSource=state.get("sql_source"),
        memoryHit=state.get("memory_hit"),
        memoryBand=state.get("memory_band"),
        metricCandidates=state.get("metric_candidates"),
        metricRecallMode=state.get("metric_recall_mode"),
        metricRecallFallback=state.get("metric_recall_fallback"),
        metricRecallReason=state.get("metric_recall_reason"),
        metricRecallConfiguredK=state.get("metric_recall_top_k"),
        metricRecallPinnedCount=state.get("metric_recall_pinned_count"),
        metricRecallEffectiveK=state.get("metric_recall_effective_k"),
        metricRecallFullCatalogCount=state.get("metric_recall_full_catalog_count"),
        metricRecallPromptCatalogCount=state.get("metric_recall_prompt_catalog_count"),
        semanticPromptChars=state.get("semantic_prompt_chars"),
        synthesisErrorCode=state.get("synthesis_error_code"),
        synthesisErrorReason=state.get("synthesis_error_reason"),
        catalogVersion=state.get("catalog_version"), lineageHash=state.get("lineage_hash"),
        metricCatalogHash=state.get("metric_catalog_hash"), schemaHash=state.get("schema_hash"),
        candidatePlans=state.get("candidate_plans"), rejectedPlans=state.get("rejected_plans"),
        selectedPlanId=state.get("selected_plan_id"),
        planSelectionSource=state.get("plan_selection_source"),
        plannerReasonCode=state.get("planner_reason_code"),
        plannerSkillVersion=state.get("planner_skill_version"),
        planValidation=state.get("plan_validation"),
        planningRetryCount=state.get("planning_retry_count"),
        lineageEdgeIds=state.get("lineage_edge_ids"),
        legacyPlannerFallback=state.get("legacy_planner_fallback"),
        plannerPromptChars=state.get("planner_prompt_chars"),
        plannerLatencyMs=state.get("planner_latency_ms"),
    )


@router.post("/runs/{run_id}/approval", response_model=AnalyzeResponse)
async def approve_run(run_id: str, request: ApprovalRequest) -> AnalyzeResponse:
    state = await resume_graph(run_id=run_id, approved=request.approved)
    if state.get("approval_status") == "rejected":
        status = "REJECTED"
    else:
        status = "SUCCESS" if state.get("final_report") else "FAILED"
    return AnalyzeResponse(
        runId=state["run_id"],
        status=status,
        finalReport=state.get("final_report") or {},
        warnings=state.get("warnings", []),
        approvalReason=state.get("approval_reason"),
        resolvedIntent=state.get("resolved_intent"),
        sqlRetryCount=state.get("sql_retry_count"),
        sqlSource=state.get("sql_source"),
        memoryHit=state.get("memory_hit"),
        memoryBand=state.get("memory_band"),
        metricCandidates=state.get("metric_candidates"),
        metricRecallMode=state.get("metric_recall_mode"),
        metricRecallFallback=state.get("metric_recall_fallback"),
        metricRecallReason=state.get("metric_recall_reason"),
        metricRecallConfiguredK=state.get("metric_recall_top_k"),
        metricRecallPinnedCount=state.get("metric_recall_pinned_count"),
        metricRecallEffectiveK=state.get("metric_recall_effective_k"),
        metricRecallFullCatalogCount=state.get("metric_recall_full_catalog_count"),
        metricRecallPromptCatalogCount=state.get("metric_recall_prompt_catalog_count"),
        semanticPromptChars=state.get("semantic_prompt_chars"),
        synthesisErrorCode=state.get("synthesis_error_code"),
        synthesisErrorReason=state.get("synthesis_error_reason"),
        catalogVersion=state.get("catalog_version"), lineageHash=state.get("lineage_hash"),
        metricCatalogHash=state.get("metric_catalog_hash"), schemaHash=state.get("schema_hash"),
        candidatePlans=state.get("candidate_plans"), rejectedPlans=state.get("rejected_plans"),
        selectedPlanId=state.get("selected_plan_id"),
        planSelectionSource=state.get("plan_selection_source"),
        plannerReasonCode=state.get("planner_reason_code"),
        plannerSkillVersion=state.get("planner_skill_version"),
        planValidation=state.get("plan_validation"),
        planningRetryCount=state.get("planning_retry_count"),
        lineageEdgeIds=state.get("lineage_edge_ids"),
        legacyPlannerFallback=state.get("legacy_planner_fallback"),
        plannerPromptChars=state.get("planner_prompt_chars"),
        plannerLatencyMs=state.get("planner_latency_ms"),
    )
