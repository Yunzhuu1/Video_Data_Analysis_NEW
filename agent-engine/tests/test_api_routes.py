import pytest

from app.api.routes import analyze, approve_run
from app.api.schemas import AnalyzeRequest, ApprovalRequest


@pytest.mark.asyncio
async def test_analyze_passthroughs_resolved_intent(monkeypatch):
    from app.api import routes

    async def fake_run(state):
        return {
            **state,
            "run_id": state["run_id"],
            "resolved_intent": {"intent": "aggregate", "metrics": ["total_plays"]},
            "sql_retry_count": 2,
            "final_report": {"summary": "s", "sql": "SELECT 1", "metrics": []},
            "warnings": [],
            "approval_status": None,
        }

    monkeypatch.setattr(routes, "run_chatbi_graph", fake_run)
    resp = await analyze(AnalyzeRequest(runId="run-1", userId="u", question="q", bypassCache=True))

    assert resp.resolved_intent == {"intent": "aggregate", "metrics": ["total_plays"]}
    assert resp.sql_retry_count == 2
    data = resp.model_dump(by_alias=True)
    assert data["resolvedIntent"] == {"intent": "aggregate", "metrics": ["total_plays"]}
    assert data["sqlRetryCount"] == 2


@pytest.mark.asyncio
async def test_analyze_omits_observations_when_absent(monkeypatch):
    from app.api import routes

    async def fake_run(state):
        return {**state, "run_id": state["run_id"], "final_report": {"summary": "s"}, "warnings": []}

    monkeypatch.setattr(routes, "run_chatbi_graph", fake_run)
    resp = await analyze(AnalyzeRequest(runId="run-1", userId="u", question="q"))

    assert resp.resolved_intent is None
    assert resp.sql_retry_count is None


@pytest.mark.asyncio
async def test_approve_run_passthroughs_resolved_intent(monkeypatch):
    from app.api import routes

    async def fake_resume(run_id, approved):
        return {
            "run_id": run_id,
            "resolved_intent": {"intent": "ranking", "metrics": ["total_plays"]},
            "sql_retry_count": 1,
            "final_report": {"summary": "s", "sql": "SELECT 1", "metrics": []},
            "warnings": [],
            "approval_status": "approved",
        }

    monkeypatch.setattr(routes, "resume_graph", fake_resume)
    resp = await approve_run("run-1", ApprovalRequest(approved=True))

    assert resp.resolved_intent == {"intent": "ranking", "metrics": ["total_plays"]}
    assert resp.sql_retry_count == 1
