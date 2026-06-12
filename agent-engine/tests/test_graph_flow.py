import pytest

from app.graph.graph_builder import resume_graph, run_chatbi_graph, run_graph
from app.settings import settings


@pytest.mark.asyncio
async def test_chatbi_graph_returns_final_report_without_attribution_branches():
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False
    state = await run_chatbi_graph(
        {
            "run_id": "run_test",
            "user_id": "demo",
            "question": "test question",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert state["route"] == "complex"
    assert state["schema_context"] == "schema_context_disabled_for_test"
    assert state["query_result"]["success"] is True
    assert state["validation_feedback"] == "PASS"
    assert "rag_result" not in state
    assert "cross_validation" not in state
    assert state["final_report"]["summary"].startswith("ChatBI answered")
    assert state["final_report"]["sql"].startswith("SELECT")


@pytest.mark.asyncio
async def test_full_graph_keeps_attribution_branches():
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False
    state = await run_graph(
        {
            "run_id": "run_full",
            "user_id": "demo",
            "question": "test question",
            "graph_mode": "full",
            "warnings": [],
            "errors": [],
        }
    )

    assert state["rag_result"]["confidence"] == 0.0
    assert state["cross_validation"].startswith("SKIPPED")
    assert state["insight_report"]["summary"].startswith("LangGraph analyzed question")
    assert state["recommendations"]
    assert state["dbqa_status"] == "pass"


@pytest.mark.asyncio
async def test_sql_retry_stops_after_success(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"count": 0}

    async def flaky_execute_sql(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            return {
                "success": False,
                "sql": kwargs["sql"],
                "columns": [],
                "rows": [],
                "rowCount": 0,
                "truncated": False,
                "warnings": [],
                "errorCode": "SQL_COMPILE_ERROR",
                "error": "bad sql",
                "riskLevel": "LOW",
                "accessedTables": [],
                "durationMs": 0,
            }
        return {
            "success": True,
            "sql": kwargs["sql"],
            "columns": ["ok"],
            "rows": [{"ok": "yes"}],
            "rowCount": 1,
            "truncated": False,
            "warnings": [],
            "errorCode": None,
            "error": None,
            "riskLevel": "LOW",
            "accessedTables": ["metric_daily"],
            "durationMs": 0,
        }

    monkeypatch.setattr(graph_builder.platform, "execute_sql", flaky_execute_sql)

    state = await run_chatbi_graph(
        {
            "run_id": "run_retry",
            "user_id": "demo",
            "question": "trend analysis",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert calls["count"] == 2
    assert state["validation_feedback"] == "PASS"
    assert state["execution_feedback"] == "PASS"
    assert state["sql_retry_count"] == 1


@pytest.mark.asyncio
async def test_hard_guard_retry_stops_after_success(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"guard": 0, "execute": 0}

    async def flaky_validate_sql(*args, **kwargs):
        calls["guard"] += 1
        if calls["guard"] == 1:
            return {
                "pass": False,
                "sql": kwargs["sql"],
                "riskLevel": "HIGH",
                "errorCode": "SQL_NOT_SELECT",
                "reason": "Only SELECT statements are allowed.",
                "suggestion": "Rewrite as SELECT.",
                "accessedTables": [],
                "violations": [{"code": "SQL_NOT_SELECT", "message": "Only SELECT"}],
            }
        return {
            "pass": True,
            "sql": kwargs["sql"],
            "riskLevel": "LOW",
            "errorCode": None,
            "reason": None,
            "suggestion": None,
            "accessedTables": ["metric_daily"],
            "violations": [],
        }

    async def execute_sql(*args, **kwargs):
        calls["execute"] += 1
        return {
            "success": True,
            "sql": kwargs["sql"],
            "columns": ["ok"],
            "rows": [{"ok": "yes"}],
            "rowCount": 1,
            "truncated": False,
            "warnings": [],
            "errorCode": None,
            "error": None,
            "riskLevel": "LOW",
            "accessedTables": ["metric_daily"],
            "durationMs": 0,
        }

    monkeypatch.setattr(graph_builder.platform, "validate_sql", flaky_validate_sql)
    monkeypatch.setattr(graph_builder.platform, "execute_sql", execute_sql)

    state = await run_chatbi_graph(
        {
            "run_id": "run_guard_retry",
            "user_id": "demo",
            "question": "trend analysis",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert calls == {"guard": 2, "execute": 1}
    assert state["hard_guard_feedback"] == "PASS"
    assert state["sql_retry_count"] == 1
    assert state["query_result"]["success"] is True


@pytest.mark.asyncio
async def test_sql_execution_stops_after_max_retries(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"execute": 0}

    async def always_fail_execute_sql(*args, **kwargs):
        calls["execute"] += 1
        return {
            "success": False,
            "sql": kwargs["sql"],
            "columns": [],
            "rows": [],
            "rowCount": 0,
            "truncated": False,
            "warnings": [],
            "errorCode": "SQL_EXECUTION_ERROR",
            "error": "Unknown column 'bad_field'",
            "riskLevel": "LOW",
            "accessedTables": ["metric_daily"],
            "durationMs": 0,
        }

    monkeypatch.setattr(graph_builder.platform, "execute_sql", always_fail_execute_sql)

    state = await run_chatbi_graph(
        {
            "run_id": "run_execution_fail",
            "user_id": "demo",
            "question": "trend analysis",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert calls["execute"] == 3
    assert state["sql_retry_count"] == 3
    assert "Unknown column" in state["execution_feedback"]
    assert state["final_report"]["summary"].startswith("ChatBI failed during SQL execution")


@pytest.mark.asyncio
async def test_dq_failure_retries_sql_generation(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"dq": 0}

    async def flaky_dq(*args, **kwargs):
        calls["dq"] += 1
        if calls["dq"] == 1:
            return {
                "pass": False,
                "riskLevel": "HIGH",
                "reason": "Trend question result lacks a time column.",
                "suggestion": "Regenerate SQL with date.",
                "warnings": [],
            }
        return {
            "pass": True,
            "riskLevel": "LOW",
            "reason": None,
            "suggestion": None,
            "warnings": [],
        }

    monkeypatch.setattr(graph_builder.platform, "check_sql_result_dq", flaky_dq)

    state = await run_chatbi_graph(
        {
            "run_id": "run_dq_retry",
            "user_id": "demo",
            "question": "trend analysis",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert calls["dq"] == 2
    assert state["sql_retry_count"] == 1
    assert state["dq_feedback"] == "PASS"


@pytest.mark.asyncio
async def test_dq_warning_continues_to_answer(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    async def warning_dq(*args, **kwargs):
        return {
            "pass": True,
            "riskLevel": "MEDIUM",
            "reason": None,
            "suggestion": None,
            "warnings": ["Result was truncated; answer should mention partial data."],
        }

    monkeypatch.setattr(graph_builder.platform, "check_sql_result_dq", warning_dq)

    state = await run_chatbi_graph(
        {
            "run_id": "run_dq_warning",
            "user_id": "demo",
            "question": "trend analysis",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert state["dq_feedback"].startswith("WARNING")
    assert state["final_report"]["warnings"] == [
        "Result was truncated; answer should mention partial data."
    ]


@pytest.mark.asyncio
async def test_hard_guard_stops_after_max_retries(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"guard": 0, "execute": 0}

    async def always_reject_sql(*args, **kwargs):
        calls["guard"] += 1
        return {
            "pass": False,
            "sql": kwargs["sql"],
            "riskLevel": "MEDIUM",
            "errorCode": "SQL_RULE_WARNING",
            "reason": "Aggregate query lacks required event_type filter.",
            "suggestion": "Add event_type filter.",
            "accessedTables": ["metric_daily"],
            "violations": [{"code": "SQL_RULE_WARNING", "message": "missing event_type"}],
        }

    async def execute_sql(*args, **kwargs):
        calls["execute"] += 1
        raise AssertionError("SQL should not execute after hard guard rejection")

    monkeypatch.setattr(graph_builder.platform, "validate_sql", always_reject_sql)
    monkeypatch.setattr(graph_builder.platform, "execute_sql", execute_sql)

    state = await run_chatbi_graph(
        {
            "run_id": "run_guard_fail",
            "user_id": "demo",
            "question": "query detail rows",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert calls == {"guard": 3, "execute": 0}
    assert state["sql_retry_count"] == 3
    assert "query_result" not in state
    assert state["final_report"]["summary"].startswith("ChatBI failed before SQL execution")


@pytest.mark.asyncio
async def test_cross_validation_uses_platform_client(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    async def high_confidence_rag(*args, **kwargs):
        return {
            "themes": ["ad"],
            "negativeRatio": 0.8,
            "representativeComments": ["drop-off after ad"],
            "summary": "users report ad impact",
            "confidence": 0.9,
        }

    async def cross_validate(rag_result):
        assert rag_result["themes"] == ["ad"]
        return "Playback cross-validation\nAd zone drop-off rate (10-25s):\n  food: 72.0%"

    monkeypatch.setattr(graph_builder.platform, "analyze_rag", high_confidence_rag)
    monkeypatch.setattr(graph_builder.platform, "cross_validate", cross_validate)

    state = await run_graph(
        {
            "run_id": "run_cross_validation",
            "user_id": "demo",
            "question": "why did food plays drop",
            "graph_mode": "full",
            "warnings": [],
            "errors": [],
        }
    )

    assert state["rag_result"]["confidence"] == 0.9
    assert "Ad zone drop-off rate" in state["cross_validation"]


@pytest.mark.asyncio
async def test_high_risk_sql_waits_for_approval_then_resumes(monkeypatch):
    settings.trace_callback_enabled = False
    settings.platform_calls_enabled = False

    from app.graph import graph_builder

    calls = {"execute": 0, "allow_high_risk": None}

    async def high_risk_validate_sql(*args, **kwargs):
        return {
            "pass": False,
            "sql": kwargs["sql"],
            "riskLevel": "HIGH",
            "errorCode": "DETAIL_QUERY_WITHOUT_LIMIT",
            "reason": "Detail table queries must include LIMIT.",
            "suggestion": "Approve only if the detail query is necessary.",
            "accessedTables": ["play_detail"],
            "violations": [{"code": "DETAIL_QUERY_WITHOUT_LIMIT", "message": "missing LIMIT"}],
        }

    async def high_risk_execute_sql(*args, **kwargs):
        calls["execute"] += 1
        calls["allow_high_risk"] = kwargs["allow_high_risk"]
        return {
            "success": True,
            "sql": kwargs["sql"],
            "columns": ["ok"],
            "rows": [{"ok": "yes"}],
            "rowCount": 1,
            "truncated": False,
            "warnings": ["detail table without time range"],
            "errorCode": None,
            "error": None,
            "riskLevel": "HIGH",
            "accessedTables": ["play_detail"],
            "durationMs": 0,
        }

    monkeypatch.setattr(graph_builder.platform, "validate_sql", high_risk_validate_sql)
    monkeypatch.setattr(graph_builder.platform, "execute_sql", high_risk_execute_sql)

    waiting_state = await run_chatbi_graph(
        {
            "run_id": "run_high_risk",
            "user_id": "demo",
            "question": "query playback details",
            "graph_mode": "chatbi",
            "warnings": [],
            "errors": [],
        }
    )

    assert waiting_state["approval_status"] == "waiting"
    assert "DETAIL_QUERY_WITHOUT_LIMIT" in waiting_state["approval_reason"]
    assert "final_report" not in waiting_state
    assert calls["execute"] == 0

    resumed_state = await resume_graph("run_high_risk", approved=True)

    assert calls == {"execute": 1, "allow_high_risk": True}
    assert resumed_state["approval_status"] == "approved"
    assert resumed_state["validation_feedback"] == "PASS"
    assert resumed_state["final_report"]["summary"].startswith("ChatBI answered")
