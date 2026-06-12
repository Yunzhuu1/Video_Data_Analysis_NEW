from app.agents.answer_agent import AnswerAgent
from app.agents.sql_agent import SQLGenerationAgent
from app.clients.platform_client import PlatformClient
from app.graph.state import DataAgentState


sql_generation_agent = SQLGenerationAgent()
answer_agent = AnswerAgent()


async def router_node(state: DataAgentState) -> DataAgentState:
    question = state["question"].lower()
    complex_keywords = (
        "why",
        "reason",
        "compare",
        "difference",
        "trend",
        "change",
        "analysis",
        "analyze",
        "ratio",
    )
    listing_keywords = ("list", "show", "display", "find")

    if any(keyword in question for keyword in complex_keywords):
        state["route"] = "complex"
    elif any(keyword in question for keyword in listing_keywords):
        state["route"] = "simple"
    else:
        state["route"] = "complex"
    return state


async def schema_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    state["schema_context"] = await platform.relevant_schema(state["question"])
    return state


async def sql_generate_node(state: DataAgentState) -> DataAgentState:
    result = await sql_generation_agent.generate(
        question=state["question"],
        schema_context=state.get("schema_context", ""),
        hard_guard_feedback=state.get("hard_guard_feedback"),
        execution_feedback=state.get("execution_feedback") or state.get("validation_feedback"),
        dq_feedback=state.get("dq_feedback"),
        sql_attempts=state.get("sql_attempts", []),
    )

    attempts = state.setdefault("sql_attempts", [])
    attempts.append(
        {
            "sql": result["sql"],
            "purpose": result.get("purpose"),
            "assumptions": result.get("assumptions", []),
            "expected_columns": result.get("expectedColumns", []),
            "success": False,
            "result_preview": None,
            "error": None,
            "hard_guard_feedback": state.get("hard_guard_feedback"),
            "warnings": [],
            "risk_level": None,
        }
    )
    return state


async def sql_hard_guard_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    attempt = state["sql_attempts"][-1]
    result = await platform.validate_sql(
        run_id=state["run_id"],
        user_id=state["user_id"],
        question=state["question"],
        sql=attempt["sql"],
        purpose=attempt.get("purpose") or "LangGraph SQL hard guard",
        allow_high_risk=False,
    )
    state["hard_guard_result"] = result
    attempt["hard_guard_result"] = result
    attempt["risk_level"] = result.get("riskLevel")

    if result.get("pass"):
        state["hard_guard_feedback"] = "PASS"
        return state

    if _requires_human_approval(result):
        state["hard_guard_feedback"] = "WAITING_APPROVAL"
        state["approval_status"] = "waiting"
        state["approval_reason"] = _format_guard_feedback(result)
        return state

    feedback = _format_guard_feedback(result)
    state["hard_guard_feedback"] = feedback
    state["sql_retry_count"] = int(state.get("sql_retry_count", 0)) + 1
    attempt["error"] = feedback
    attempt["success"] = False
    errors = state.setdefault("errors", [])
    errors.append(feedback)
    return state


def _requires_human_approval(result: dict) -> bool:
    if str(result.get("riskLevel", "")).upper() != "HIGH":
        return False
    retryable_codes = {
        "SQL_EMPTY",
        "SQL_NOT_SELECT",
        "SQL_PARSE_ERROR",
        "SQL_SYNTAX_ERROR",
        "SQL_RULE_WARNING",
    }
    approval_codes = {
        "DETAIL_QUERY_WITHOUT_LIMIT",
        "DETAIL_QUERY_WITHOUT_TIME_RANGE",
        "SQL_FULL_SCAN",
        "SQL_LARGE_SCAN",
        "SQL_CIRCUIT_BREAKER",
        "SENSITIVE_FIELD_ACCESS",
    }
    codes = [str(result.get("errorCode") or "")]
    for violation in result.get("violations") or []:
        if isinstance(violation, dict):
            codes.append(str(violation.get("code") or ""))
    if any(code in retryable_codes for code in codes):
        return False
    return any(code in approval_codes for code in codes)


async def sql_execute_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    attempt = state["sql_attempts"][-1]
    result = await platform.execute_sql(
        run_id=state["run_id"],
        user_id=state["user_id"],
        question=state["question"],
        sql=attempt["sql"],
        purpose=attempt.get("purpose") or "LangGraph SQL execution",
        allow_high_risk=state.get("approval_status") == "approved",
    )
    state["query_result"] = result
    attempt["success"] = bool(result.get("success"))
    attempt["result_preview"] = str(result.get("rows", []))[:500]
    attempt["error"] = result.get("error")
    attempt["warnings"] = result.get("warnings", [])
    attempt["risk_level"] = result.get("riskLevel")
    return state


def _format_guard_feedback(result: dict) -> str:
    error_code = result.get("errorCode") or "SQL_HARD_GUARD_FAILED"
    reason = result.get("reason") or "SQL hard guard failed"
    suggestion = result.get("suggestion") or "Regenerate SQL."
    violations = result.get("violations") or []
    violation_text = "; ".join(
        f"{item.get('code')}: {item.get('message')}" for item in violations if isinstance(item, dict)
    )
    if violation_text:
        return f"{error_code}: {reason}. Suggestion: {suggestion}. Violations: {violation_text}"
    return f"{error_code}: {reason}. Suggestion: {suggestion}"


async def sql_validate_node(state: DataAgentState) -> DataAgentState:
    result = state.get("query_result") or {}
    if result.get("success"):
        state["validation_feedback"] = "PASS"
        state["execution_feedback"] = "PASS"
    else:
        feedback = _format_execution_feedback(result)
        state["validation_feedback"] = feedback
        state["execution_feedback"] = feedback
        state["sql_retry_count"] = int(state.get("sql_retry_count", 0)) + 1
        errors = state.setdefault("errors", [])
        errors.append(feedback)
    return state


async def sql_soft_dq_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    result = await platform.check_sql_result_dq(
        run_id=state["run_id"],
        user_id=state["user_id"],
        question=state["question"],
        query_result=state.get("query_result") or {},
    )
    state["dq_result"] = result

    if result.get("pass"):
        warnings = result.get("warnings") or []
        if warnings:
            state.setdefault("warnings", []).extend(str(warning) for warning in warnings)
            state["dq_feedback"] = "WARNING: " + "; ".join(str(warning) for warning in warnings)
        else:
            state["dq_feedback"] = "PASS"
        return state

    feedback = _format_dq_feedback(result)
    state["dq_feedback"] = feedback
    state["sql_retry_count"] = int(state.get("sql_retry_count", 0)) + 1
    errors = state.setdefault("errors", [])
    errors.append(feedback)
    return state


def _format_dq_feedback(result: dict) -> str:
    reason = result.get("reason") or "SQL result failed DQ check"
    suggestion = result.get("suggestion") or "Regenerate SQL so the result can answer the question."
    return f"DQ_FAILED: {reason}. Suggestion: {suggestion}"


def _format_execution_feedback(result: dict) -> str:
    error_code = result.get("errorCode") or "SQL_EXECUTION_FAILED"
    error = result.get("error") or result.get("resultText") or "SQL execution failed"
    suggestion = _execution_suggestion(error_code, error)
    return f"{error_code}: {error}. Suggestion: {suggestion}"


def _execution_suggestion(error_code: str, error: str) -> str:
    text = f"{error_code} {error}".lower()
    if "unknown column" in text:
        return "Use only columns present in schema_context."
    if "syntax" in text or "parse" in text:
        return "Fix MySQL syntax and return a valid SELECT statement."
    if "timeout" in text:
        return "Add filters, aggregate earlier, or reduce scanned rows."
    if "full_scan" in text or "large_scan" in text:
        return "Add WHERE filters or query metric_daily instead of detail tables."
    return "Regenerate SQL according to the error and schema_context."


async def rag_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    rag_result = await platform.analyze_rag(state["question"], state.get("query_result") or {})
    state["rag_result"] = {
        "themes": rag_result.get("themes") or [],
        "negative_ratio": rag_result.get("negativeRatio", rag_result.get("negative_ratio", 0.0)),
        "representative_comments": rag_result.get(
            "representativeComments", rag_result.get("representative_comments", [])
        ),
        "summary": rag_result.get("summary", ""),
        "confidence": rag_result.get("confidence", 0.0),
    }
    return state


async def cross_validation_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    state["cross_validation"] = await platform.cross_validate(state.get("rag_result") or {})
    return state


async def insight_node(state: DataAgentState) -> DataAgentState:
    query_result = state.get("query_result") or {}
    rag_result = state.get("rag_result") or {}
    state["insight_report"] = {
        "summary": (
            f"LangGraph analyzed question: {state['question']} "
            f"(route={state.get('route')}, schemaReady={bool(state.get('schema_context'))}, "
            f"sqlStatus={query_result.get('success')}, ragConfidence={rag_result.get('confidence')}, "
            f"crossValidation={state.get('cross_validation')})"
        ),
        "period": "-",
        "metrics": [],
        "charts": [],
    }
    return state


async def recommendation_node(state: DataAgentState) -> DataAgentState:
    query_result = state.get("query_result") or {}
    recommendations: list[str] = []
    if query_result.get("success"):
        recommendations.append("Continue validating business context with SQL Gateway results.")
    rag_result = state.get("rag_result") or {}
    if float(rag_result.get("confidence") or 0.0) < 0.5:
        recommendations.append("RAG evidence confidence is low; avoid strong attribution claims.")
    state["recommendations"] = recommendations[:3]
    return state


async def merge_node(state: DataAgentState) -> DataAgentState:
    report = dict(state.get("insight_report") or {})
    report["recommendations"] = state.get("recommendations", [])
    state["final_report"] = report
    return state


async def answer_node(state: DataAgentState) -> DataAgentState:
    query_result = state.get("query_result") or {}
    attempts = state.get("sql_attempts") or []
    last_attempt = attempts[-1] if attempts else {}
    hard_guard_failed = state.get("hard_guard_feedback") not in (None, "PASS") and not query_result
    execution_failed = state.get("execution_feedback") not in (None, "PASS") and not query_result.get("success")

    if hard_guard_failed:
        report = {
            "summary": f"ChatBI failed before SQL execution: {state.get('hard_guard_feedback')}",
            "sql": last_attempt.get("sql"),
            "metrics": [],
            "charts": [],
            "recommendations": [],
            "warnings": list(state.get("warnings", [])),
        }
    elif execution_failed:
        report = {
            "summary": f"ChatBI failed during SQL execution: {state.get('execution_feedback')}",
            "sql": last_attempt.get("sql"),
            "metrics": [],
            "charts": [],
            "recommendations": [],
            "warnings": list(state.get("warnings", [])),
        }
    else:
        report = await answer_agent.generate(
            question=state["question"],
            query_result=query_result,
            sql=last_attempt.get("sql"),
            dq_result=state.get("dq_result"),
            warnings=list(state.get("warnings", [])),
        )
    report["dq"] = state.get("dq_result")
    state["final_report"] = report
    return state


async def dbqa_node(state: DataAgentState) -> DataAgentState:
    report = state.get("final_report") or {}
    missing: list[str] = []
    if not report.get("summary"):
        missing.append("summary")
    if "recommendations" not in report:
        missing.append("recommendations")
    if state.get("query_result") is None:
        missing.append("query_result")

    if missing:
        state["dbqa_status"] = "fail"
        state["dbqa_feedback"] = "Missing fields: " + ", ".join(missing)
    else:
        state["dbqa_status"] = "pass"
        state["dbqa_feedback"] = "PASS"
    return state
