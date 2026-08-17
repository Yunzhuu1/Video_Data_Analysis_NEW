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

    model_config = {"populate_by_name": True}


class ApprovalRequest(BaseModel):
    approved: bool


class HealthResponse(BaseModel):
    status: Literal["UP"]
    service: str
