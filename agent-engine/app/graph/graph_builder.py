from functools import wraps

from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.clients.platform_client import PlatformClient
from app.graph.nodes import (
    answer_node,
    plan_enumerate_node,
    plan_select_node,
    plan_validate_node,
    router_node,
    schema_node,
    semantic_resolve_node,
    sql_execute_node,
    sql_generate_node,
    sql_hard_guard_node,
    sql_soft_dq_node,
    sql_synthesize_node,
)
from app.graph.state import DataAgentState

MAX_SQL_RETRIES = 3

platform = PlatformClient()


async def init_memory(db_path: str, backend: str | None = None) -> None:
    """启动时注入语义记忆（nodes.memory）。失败仅告警，不阻断服务。

    backend 默认取 settings.memory_store_backend；lance 需要真实路径 + 方舟 key，
    :memory: 或未配 key → 自动降级 sqlite（不改变既有行为）。
    """
    from app.graph import nodes
    from app.memory.embeddings import get_embedding_provider
    from app.memory.vector_store import build_memory_store
    from app.settings import settings

    backend = backend or settings.memory_store_backend
    if backend == "lance" and (db_path == ":memory:" or not get_embedding_provider().available()):
        backend = "sqlite"
    try:
        store = await build_memory_store(
            db_path, backend=backend,
            provider=get_embedding_provider() if backend == "lance" else None,
            embedding_model=settings.ark_embedding_model)
        nodes.memory = store
        if backend == "lance":
            print(f"[memory] lance store ready: {db_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"[memory] init failed, memory disabled: {exc}")
        nodes.memory = None


# ---------------------------------------------------------------------------
# Trace wrapper: keeps the Run Trace contract (start/finish/fail callbacks).
# ---------------------------------------------------------------------------
def traced(node_name: str):
    """Wrap a graph node with Run Trace callbacks (start/finish/fail)."""

    def deco(fn):
        @wraps(fn)
        async def wrapped(state: DataAgentState) -> DataAgentState:
            run_id = state["run_id"]
            node_id = await platform.start_node(
                run_id=run_id,
                node_name=node_name,
                input_payload={"question": state["question"], "route": state.get("route")},
            )
            try:
                next_state = await fn(state)
            except GraphInterrupt:
                # HITL interrupt is not a node failure; let the runtime handle it.
                raise
            except Exception as exc:
                await platform.fail_node(run_id=run_id, node_id=node_id, error_message=str(exc))
                raise
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
                    "dq_result": next_state.get("dq_result"),
                    "dq_feedback": next_state.get("dq_feedback"),
                    "final_report": next_state.get("final_report"),
                    "catalog_version": next_state.get("catalog_version"),
                    "candidate_plans": next_state.get("candidate_plans"),
                    "rejected_plans": next_state.get("rejected_plans"),
                    "selected_plan_id": next_state.get("selected_plan_id"),
                    "plan_selection_source": next_state.get("plan_selection_source"),
                    "plan_validation": next_state.get("plan_validation"),
                    "planning_retry_count": next_state.get("planning_retry_count"),
                    "lineage_edge_ids": next_state.get("lineage_edge_ids"),
                },
            )
            return next_state

        return wrapped

    return deco


# ---------------------------------------------------------------------------
# Node adapters: bind the shared platform client so nodes are (state) -> state.
# ---------------------------------------------------------------------------
async def _schema(state: DataAgentState) -> DataAgentState:
    return await schema_node(state, platform)


async def _hard_guard(state: DataAgentState) -> DataAgentState:
    return await sql_hard_guard_node(state, platform)


async def _execute(state: DataAgentState) -> DataAgentState:
    return await sql_execute_node(state, platform)


async def _soft_dq(state: DataAgentState) -> DataAgentState:
    return await sql_soft_dq_node(state, platform)


async def _semantic_resolve(state: DataAgentState) -> DataAgentState:
    return await semantic_resolve_node(state, platform)


async def _synthesize(state: DataAgentState) -> DataAgentState:
    return await sql_synthesize_node(state, platform)


async def _plan_enumerate(state: DataAgentState) -> DataAgentState:
    return await plan_enumerate_node(state, platform)


# ---------------------------------------------------------------------------
# Human-in-the-loop approval node: pauses via interrupt() until an operator
# approves/rejects. The resume value comes from Command(resume=...) and decides
# whether the approved SQL proceeds to execution.
# ---------------------------------------------------------------------------
async def approval_node(state: DataAgentState) -> DataAgentState:
    attempts = state.get("sql_attempts") or []
    last_sql = attempts[-1].get("sql") if attempts else None
    decision = interrupt(
        {
            "runId": state["run_id"],
            "sql": last_sql,
            "approvalReasons": state.get("approval_reason"),
        }
    )
    if decision:
        return {"approval_status": "approved"}
    return {
        "approval_status": "rejected",
        "final_report": {
            "summary": "Analysis stopped because the high-risk SQL was rejected.",
            "period": "-",
            "metrics": [],
            "charts": [],
            "recommendations": [],
        },
    }


# ---------------------------------------------------------------------------
# Conditional edge routing (the graph's control flow).
# ---------------------------------------------------------------------------
def route_after_resolve(state: DataAgentState) -> str:
    return "plan" if state.get("semantic_ok") else "generate"


def route_after_enumerate(state: DataAgentState) -> str:
    return "select" if state.get("plan_selection_source") == "PLANNER_AGENT" else "validate"


def route_after_plan_validate(state: DataAgentState) -> str:
    verdict = (state.get("plan_validation") or {}).get("verdict")
    if verdict == "REPLAN" and int(state.get("planning_retry_count", 0)) <= 1:
        return "select"
    return "synthesize"


def route_after_synthesize(state: DataAgentState) -> str:
    # synthesis failure (e.g. unsupported intent) degrades to raw generation
    return "guard" if state.get("semantic_ok") else "generate"


def route_after_hard_guard(state: DataAgentState) -> str:
    if state.get("approval_status") == "waiting":
        return "approval"
    if state.get("hard_guard_feedback") == "PASS":
        return "execute"
    if int(state.get("sql_retry_count", 0)) >= MAX_SQL_RETRIES:
        return "answer"
    return "generate"


def route_after_approval(state: DataAgentState) -> str:
    return "execute" if state.get("approval_status") == "approved" else "end"


def route_after_execute(state: DataAgentState) -> str:
    if state.get("execution_feedback") == "PASS":
        return "dq"
    if state.get("approval_status") == "approved":
        # Approved runs must not regenerate SQL (approval-object drift).
        return "answer"
    if int(state.get("sql_retry_count", 0)) >= MAX_SQL_RETRIES:
        return "answer"
    return "generate"


def route_after_dq(state: DataAgentState) -> str:
    dq = state.get("dq_feedback")
    if dq == "PASS" or str(dq or "").startswith("WARNING"):
        return "answer"
    if state.get("approval_status") == "approved":
        # Approved runs must not regenerate SQL (approval-object drift).
        return "answer"
    if int(state.get("sql_retry_count", 0)) >= MAX_SQL_RETRIES:
        return "answer"
    return "generate"


# ---------------------------------------------------------------------------
# Graph construction.
# ---------------------------------------------------------------------------
def build_graph(checkpointer):
    """Build and compile the ChatBI state graph."""
    graph = StateGraph(DataAgentState)
    graph.add_node("ROUTER", traced("ROUTER")(router_node))
    graph.add_node("SCHEMA", traced("SCHEMA")(_schema))
    graph.add_node("SEMANTIC_RESOLVE", traced("SEMANTIC_RESOLVE")(_semantic_resolve))
    graph.add_node("PLAN_ENUMERATE", traced("PLAN_ENUMERATE")(_plan_enumerate))
    graph.add_node("PLAN_SELECT", traced("PLAN_SELECT")(plan_select_node))
    graph.add_node("PLAN_VALIDATE", traced("PLAN_VALIDATE")(plan_validate_node))
    graph.add_node("SQL_SYNTHESIZE", traced("SQL_SYNTHESIZE")(_synthesize))
    graph.add_node("SQL_GENERATE", traced("SQL_GENERATE")(sql_generate_node))
    graph.add_node("SQL_HARD_GUARD", traced("SQL_HARD_GUARD")(_hard_guard))
    graph.add_node("SQL_EXECUTE", traced("SQL_EXECUTE")(_execute))
    graph.add_node("SQL_SOFT_DQ", traced("SQL_SOFT_DQ")(_soft_dq))
    # APPROVAL is intentionally untraced: interrupt() pauses inside it and the
    # resume re-runs it, which would otherwise create duplicate trace rows.
    graph.add_node("APPROVAL", approval_node)
    graph.add_node("ANSWER", traced("ANSWER")(answer_node))

    graph.add_edge(START, "ROUTER")
    graph.add_edge("ROUTER", "SCHEMA")
    graph.add_edge("SCHEMA", "SEMANTIC_RESOLVE")
    graph.add_conditional_edges(
        "SEMANTIC_RESOLVE",
        route_after_resolve,
        {"plan": "PLAN_ENUMERATE", "generate": "SQL_GENERATE"},
    )
    graph.add_conditional_edges(
        "PLAN_ENUMERATE", route_after_enumerate,
        {"select": "PLAN_SELECT", "validate": "PLAN_VALIDATE"},
    )
    graph.add_edge("PLAN_SELECT", "PLAN_VALIDATE")
    graph.add_conditional_edges(
        "PLAN_VALIDATE", route_after_plan_validate,
        {"select": "PLAN_SELECT", "synthesize": "SQL_SYNTHESIZE"},
    )
    graph.add_conditional_edges(
        "SQL_SYNTHESIZE",
        route_after_synthesize,
        {"guard": "SQL_HARD_GUARD", "generate": "SQL_GENERATE"},
    )
    graph.add_edge("SQL_GENERATE", "SQL_HARD_GUARD")

    graph.add_conditional_edges(
        "SQL_HARD_GUARD",
        route_after_hard_guard,
        {
            "approval": "APPROVAL",
            "execute": "SQL_EXECUTE",
            "answer": "ANSWER",
            "generate": "SQL_GENERATE",
        },
    )
    graph.add_conditional_edges(
        "APPROVAL",
        route_after_approval,
        {"execute": "SQL_EXECUTE", "end": END},
    )
    graph.add_conditional_edges(
        "SQL_EXECUTE",
        route_after_execute,
        {"dq": "SQL_SOFT_DQ", "answer": "ANSWER", "generate": "SQL_GENERATE"},
    )
    graph.add_conditional_edges(
        "SQL_SOFT_DQ",
        route_after_dq,
        {"answer": "ANSWER", "generate": "SQL_GENERATE"},
    )
    graph.add_edge("ANSWER", END)

    return graph.compile(checkpointer=checkpointer)


compiled_graph = None


def init_graph(checkpointer) -> None:
    """Set the compiled graph used by the facades (called at app startup / tests)."""
    global compiled_graph
    compiled_graph = build_graph(checkpointer)


def _config(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


async def run_chatbi_graph(initial_state: DataAgentState) -> DataAgentState:
    """Run the ChatBI main line. Thread id == run id (stable across restarts)."""
    if compiled_graph is None:
        raise RuntimeError("graph not initialized; call init_graph(checkpointer) first")
    return await compiled_graph.ainvoke(initial_state, config=_config(initial_state["run_id"]))


async def resume_graph(run_id: str, approved: bool) -> DataAgentState:
    """Resume a run paused at the approval interrupt."""
    if compiled_graph is None:
        raise RuntimeError("graph not initialized; call init_graph(checkpointer) first")
    return await compiled_graph.ainvoke(Command(resume=approved), config=_config(run_id))
