from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    run_id: str = Field(alias="runId")
    user_id: str = Field(alias="userId")
    question: str
    bypass_cache: bool = Field(default=False, alias="bypassCache")
    graph_mode: Literal["chatbi", "full"] = Field(default="chatbi", alias="graphMode")

    model_config = {"populate_by_name": True}


class AnalyzeResponse(BaseModel):
    run_id: str = Field(alias="runId")
    status: Literal["SUCCESS", "FAILED", "WAITING_APPROVAL", "REJECTED"]
    final_report: dict[str, Any] = Field(alias="finalReport")
    warnings: list[str] = []
    approval_reason: str | None = Field(default=None, alias="approvalReason")

    model_config = {"populate_by_name": True}


class ApprovalRequest(BaseModel):
    approved: bool


class HealthResponse(BaseModel):
    status: Literal["UP"]
    service: str
