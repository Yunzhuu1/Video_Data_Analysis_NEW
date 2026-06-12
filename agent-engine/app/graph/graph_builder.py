from app.clients.platform_client import PlatformClient
from app.graph.checkpoints import checkpoint_store
from app.graph.nodes import (
    answer_node,
    cross_validation_node,
    dbqa_node,
    insight_node,
    merge_node,
    rag_node,
    recommendation_node,
    router_node,
    schema_node,
    sql_execute_node,
    sql_generate_node,
    sql_hard_guard_node,
    sql_soft_dq_node,
    sql_validate_node,
)
from app.graph.state import DataAgentState


platform = PlatformClient()


async def run_graph(initial_state: DataAgentState) -> DataAgentState:
    """Run the legacy full graph with RAG, cross-validation, recommendations and DBQA."""
    state = await traced_node(initial_state, "ROUTER", router_node)
    state = await traced_node(state, "SCHEMA", lambda s: schema_node(s, platform))

    while True:
        state = await traced_node(state, "SQL_GENERATE", sql_generate_node)
        state = await traced_node(state, "SQL_HARD_GUARD", lambda s: sql_hard_guard_node(s, platform))
        if state.get("approval_status") == "waiting":
            checkpoint_store.save(state["run_id"], state)
            return state
        if state.get("hard_guard_feedback") != "PASS":
            if int(state.get("sql_retry_count", 0)) >= 3:
                state = await traced_node(state, "ANSWER", answer_node)
                return state
            continue
        state = await traced_node(state, "SQL_EXECUTE", lambda s: sql_execute_node(s, platform))
        state = await traced_node(state, "SQL_VALIDATE", sql_validate_node)
        if state.get("validation_feedback") == "PASS":
            state = await traced_node(state, "SQL_SOFT_DQ", lambda s: sql_soft_dq_node(s, platform))
            if state.get("dq_feedback") == "PASS" or str(state.get("dq_feedback", "")).startswith("WARNING"):
                break
            if int(state.get("sql_retry_count", 0)) >= 3:
                state = await traced_node(state, "ANSWER", answer_node)
                return state
            continue
        if int(state.get("sql_retry_count", 0)) >= 3:
            state = await traced_node(state, "ANSWER", answer_node)
            return state
        continue

    state = await traced_node(state, "RAG", lambda s: rag_node(s, platform))
    state = await traced_node(state, "CROSS_VALIDATE", lambda s: cross_validation_node(s, platform))
    state = await traced_node(state, "INSIGHT", insight_node)
    state = await traced_node(state, "RECOMMENDATION", recommendation_node)
    state = await traced_node(state, "MERGE", merge_node)
    state = await traced_node(state, "DBQA", dbqa_node)
    return state


async def run_chatbi_graph(initial_state: DataAgentState) -> DataAgentState:
    """Run the default ChatBI graph without attribution side branches."""
    state = await traced_node(initial_state, "ROUTER", router_node)
    state = await traced_node(state, "SCHEMA", lambda s: schema_node(s, platform))

    while True:
        state = await traced_node(state, "SQL_GENERATE", sql_generate_node)
        state = await traced_node(state, "SQL_HARD_GUARD", lambda s: sql_hard_guard_node(s, platform))
        if state.get("approval_status") == "waiting":
            checkpoint_store.save(state["run_id"], state)
            return state
        if state.get("hard_guard_feedback") != "PASS":
            if int(state.get("sql_retry_count", 0)) >= 3:
                state = await traced_node(state, "ANSWER", answer_node)
                return state
            continue
        state = await traced_node(state, "SQL_EXECUTE", lambda s: sql_execute_node(s, platform))
        state = await traced_node(state, "SQL_VALIDATE", sql_validate_node)
        if state.get("validation_feedback") == "PASS":
            state = await traced_node(state, "SQL_SOFT_DQ", lambda s: sql_soft_dq_node(s, platform))
            if state.get("dq_feedback") == "PASS" or str(state.get("dq_feedback", "")).startswith("WARNING"):
                break
            if int(state.get("sql_retry_count", 0)) >= 3:
                state = await traced_node(state, "ANSWER", answer_node)
                return state
            continue
        if int(state.get("sql_retry_count", 0)) >= 3:
            state = await traced_node(state, "ANSWER", answer_node)
            return state
        continue

    state = await traced_node(state, "ANSWER", answer_node)
    return state


async def resume_graph(run_id: str, approved: bool) -> DataAgentState:
    state = checkpoint_store.get(run_id)
    if state is None:
        raise ValueError(f"checkpoint not found for run_id={run_id}")

    if not approved:
        state["approval_status"] = "rejected"
        state["final_report"] = {
            "summary": "Analysis stopped because the high-risk SQL was rejected.",
            "period": "-",
            "metrics": [],
            "charts": [],
            "recommendations": [],
        }
        checkpoint_store.delete(run_id)
        return state

    state["approval_status"] = "approved"
    state = await traced_node(state, "SQL_EXECUTE", lambda s: sql_execute_node(s, platform))
    state = await traced_node(state, "SQL_VALIDATE", sql_validate_node)
    if state.get("validation_feedback") != "PASS":
        state = await traced_node(state, "ANSWER", answer_node)
        checkpoint_store.delete(run_id)
        return state
    state = await traced_node(state, "SQL_SOFT_DQ", lambda s: sql_soft_dq_node(s, platform))
    if state.get("dq_feedback") not in ("PASS", None) and not str(state.get("dq_feedback", "")).startswith("WARNING"):
        state = await traced_node(state, "ANSWER", answer_node)
        checkpoint_store.delete(run_id)
        return state

    if state.get("graph_mode", "chatbi") == "chatbi":
        state = await traced_node(state, "ANSWER", answer_node)
        checkpoint_store.delete(run_id)
        return state

    state = await traced_node(state, "RAG", lambda s: rag_node(s, platform))
    state = await traced_node(state, "CROSS_VALIDATE", lambda s: cross_validation_node(s, platform))
    state = await traced_node(state, "INSIGHT", insight_node)
    state = await traced_node(state, "RECOMMENDATION", recommendation_node)
    state = await traced_node(state, "MERGE", merge_node)
    state = await traced_node(state, "DBQA", dbqa_node)
    checkpoint_store.delete(run_id)
    return state


async def traced_node(state: DataAgentState, node_name: str, fn) -> DataAgentState:
    run_id = state["run_id"]
    node_id = await platform.start_node(
        run_id=run_id,
        node_name=node_name,
        input_payload={"question": state["question"], "route": state.get("route")},
    )
    try:
        next_state = await fn(state)
        await platform.finish_node(
            run_id=run_id,
            node_id=node_id,
            output_payload={
                "route": next_state.get("route"),
                "schema_context": next_state.get("schema_context"),
                "sql_attempts": next_state.get("sql_attempts"),
                "hard_guard_result": next_state.get("hard_guard_result"),
                "hard_guard_feedback": next_state.get("hard_guard_feedback"),
                "query_result": next_state.get("query_result"),
                "validation_feedback": next_state.get("validation_feedback"),
                "dq_result": next_state.get("dq_result"),
                "dq_feedback": next_state.get("dq_feedback"),
                "rag_result": next_state.get("rag_result"),
                "cross_validation": next_state.get("cross_validation"),
                "insight_report": next_state.get("insight_report"),
                "recommendations": next_state.get("recommendations"),
                "final_report": next_state.get("final_report"),
                "dbqa_status": next_state.get("dbqa_status"),
                "dbqa_feedback": next_state.get("dbqa_feedback"),
            },
        )
        return next_state
    except Exception as exc:
        await platform.fail_node(run_id=run_id, node_id=node_id, error_message=str(exc))
        raise
