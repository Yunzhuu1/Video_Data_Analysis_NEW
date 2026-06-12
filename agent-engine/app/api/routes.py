from fastapi import APIRouter

from app.api.schemas import AnalyzeRequest, AnalyzeResponse, ApprovalRequest, HealthResponse
from app.graph.graph_builder import resume_graph, run_chatbi_graph, run_graph
from app.settings import settings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="UP", service=settings.service_name)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    graph_runner = run_graph if request.graph_mode == "full" else run_chatbi_graph
    state = await graph_runner(
        {
            "run_id": request.run_id,
            "user_id": request.user_id,
            "question": request.question,
            "bypass_cache": request.bypass_cache,
            "graph_mode": request.graph_mode,
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
    )
