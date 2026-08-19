import logging

from app.agents.answer_agent import AnswerAgent
from app.agents.semantic_resolver import SemanticResolver
from app.agents.sql_agent import SQLGenerationAgent
from app.clients.platform_client import PlatformClient
from app.graph.state import DataAgentState
from app.memory.aliases import get_aliases
from app.memory.embeddings import get_embedding_provider
from app.memory.retriever import (
    build_retriever,
    hit_allowed,
    normalize_question,
)
from app.memory.store import MemoryStore, compute_resolver_hash
from app.settings import settings
from app.synthesis.sql_synthesizer import DIMENSIONS, SynthesisError, synthesize

sql_generation_agent = SQLGenerationAgent()
answer_agent = AnswerAgent()
semantic_resolver = SemanticResolver()

# 语义记忆（由 graph_builder.init_memory 在启动时注入；None = 未启用）
memory: MemoryStore | None = None

logger = logging.getLogger(__name__)


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
        execution_feedback=state.get("execution_feedback"),
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
            "source": "fallback",
        }
    )
    state["sql_source"] = "fallback"
    return state

def _acceptable_intent(intent: dict) -> bool:
    return bool(
        intent.get("metrics")
        and intent.get("intent") in {"aggregate", "trend", "ranking", "detail"}
        and float(intent.get("confidence") or 0.0) >= 0.5
    )


async def _memory_pre_resolve(state: DataAgentState, catalog: list[dict]):
    """记忆前置：hit → 直通复用；inject → few-shot；失败静默降级。返回处理后的 state 或 None。"""
    if memory is None or not settings.memory_enabled:
        return None
    try:
        retriever = build_retriever(memory, get_embedding_provider())
        hits = await retriever.search(state["question"], namespace=state.get("memory_namespace", "default"))
        if not hits:
            return None
        best = hits[0]
        if best.band == "hit" and hit_allowed(state["question"], best.entry, catalog, get_aliases()):
            intent = best.entry.resolved_intent
            state["resolved_intent"] = intent
            state["semantic_ok"] = True
            state["sql_source"] = "memory"
            state["memory_hit"] = True
            state["memory_band"] = "hit"
            if best.entry.id is not None:
                await memory.record_hit(best.entry.id)
            return state
        # acceptable 复检不过 → 降级 miss（走正常 LLM）
        if best.band == "hit":
            state["memory_band"] = "hit_rejected"
            return None
        if best.band == "inject":
            # 示例按 intent 去重（P2-2）：top-3 尽量覆盖不同 intent，同 intent 只取相似度最高一条（hits 已按分数降序）
            examples: list[tuple[str, dict]] = []
            seen_intents: set[str] = set()
            for h in hits:
                it = str((h.entry.resolved_intent or {}).get("intent") or "")
                if it in seen_intents:
                    continue
                seen_intents.add(it)
                examples.append((h.entry.norm_question, h.entry.resolved_intent))
                if len(examples) >= 3:
                    break
            state["memory_band"] = "inject"
            try:
                intent = await semantic_resolver.resolve(
                    question=state["question"], catalog=catalog, dimensions=DIMENSIONS,
                    examples=examples)
            except Exception:  # noqa: BLE001
                intent = None
            if intent is None:
                state["semantic_ok"] = False
                return state
            acceptable = _acceptable_intent(intent)
            state["resolved_intent"] = intent
            state["semantic_ok"] = acceptable
            return state
    except Exception:  # noqa: BLE001 - 记忆失败不打断主链路
        return None
    return None


async def semantic_resolve_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    """LLM 只做语义匹配：把问题解析为结构化 ResolvedIntent（不写 SQL）。"""
    catalog = await platform.metric_catalog()
    catalog = catalog or []
    handled = await _memory_pre_resolve(state, catalog)
    if handled is not None:
        return handled
    try:
        intent = await semantic_resolver.resolve(
            question=state["question"],
            catalog=catalog,
            dimensions=DIMENSIONS,
        )
    except Exception:  # noqa: BLE001 - degrade to raw SQL generation
        intent = None
    if intent is None:
        state["semantic_ok"] = False
        return state

    acceptable = _acceptable_intent(intent)
    state["resolved_intent"] = intent
    state["semantic_ok"] = acceptable
    return state


async def _expand_relative_time(relative: dict, metric_defs: dict, intent: dict,
                                  state: DataAgentState, platform: PlatformClient) -> dict:
    """合成前 relative → absolute：锚点 = 数据末日（P2-1 同源：_resolve_path 后 source 的 timeField）。

    - real：platform.execute_sql 查 MAX(时间列)（走 Spring SQL 网关，符合"Python 不直连库"）。
    - mock：固定锚点 2023-10-31（与 seed 42 数据末日一致）。
    """
    from app.synthesis.sql_synthesizer import _ALIAS, _field_expr, _resolve_path
    from app.synthesis.time_expand import time_expand

    codes = list(intent.get("metrics") or [])
    mdef = metric_defs.get(codes[0]) if codes else None
    if mdef is None:
        raise ValueError("no metric def for anchor query")
    path = _resolve_path(mdef, intent.get("intent", "aggregate"), list(intent.get("dimensions") or []))
    source = path["source"]
    tcol = mdef.get("timeField") or "date"
    rel_inner = relative.get("relative") or relative  # time_range 可能是 {type, relative:{...}, granularity}
    if not settings.platform_calls_enabled:  # mock 固定锚点（seed 42 数据末日）
        expanded = time_expand(rel_inner, "2023-10-31")
        expanded["granularity"] = relative.get("granularity") or rel_inner.get("granularity")
        return expanded
    expr, joins = _field_expr(source, tcol)
    alias = _ALIAS.get(source, source)
    join_sql = (" " + " ".join(dict.fromkeys(joins))) if joins else ""
    sql = f"SELECT MAX({expr}) FROM {source} {alias}{join_sql}"
    qr = await platform.execute_sql(
        run_id=state.get("run_id", ""), user_id=state.get("user_id", "eval"),
        question=state.get("question", ""), sql=sql, purpose="anchor_time")
    rows = qr.get("rows") or []
    if not rows:
        raise ValueError("anchor query returned no rows")
    anchor = str(next(iter(rows[0].values())))
    expanded = time_expand(rel_inner, anchor)
    expanded["granularity"] = relative.get("granularity") or rel_inner.get("granularity")
    return expanded


async def sql_synthesize_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    """按 ResolvedIntent + 指标字典确定性合成 SQL。"""
    intent = state.get("resolved_intent") or {}
    metric_defs = {}
    for code in intent.get("metrics") or []:
        try:
            metric_defs[code] = await platform.metric_definition(code)
        except Exception:  # noqa: BLE001 - degrade to raw SQL generation
            state["semantic_ok"] = False
            return state

    # relative 时间展开（合成前，P2-1 同源锚点；失败降级 + warning，不打断主链路）
    tr = intent.get("time_range") or {}
    if tr.get("type") == "relative":
        try:
            intent["time_range"] = await _expand_relative_time(tr, metric_defs, intent, state, platform)
            state["resolved_intent"] = intent
        except Exception as exc:  # noqa: BLE001
            logger.warning("relative time expand failed: %s", exc)

    try:
        sql = synthesize(intent, metric_defs)
    except (SynthesisError, KeyError, TypeError, ValueError):
        state["semantic_ok"] = False
        return state

    attempts = state.setdefault("sql_attempts", [])
    attempts.append(
        {
            "sql": sql,
            "purpose": f"Semantic synthesis for {intent.get('metrics')}",
            "assumptions": [f"source={metric_defs.get(intent['metrics'][0], {}).get('sourceTable')}"],
            "expected_columns": list(intent.get("dimensions") or []) + list(intent.get("metrics") or []),
            "success": False,
            "result_preview": None,
            "error": None,
            "hard_guard_feedback": state.get("hard_guard_feedback"),
            "warnings": [],
            "risk_level": None,
            "source": "semantic",
        }
    )
    if state.get("sql_source") != "memory":
        # 记忆命中的 intent 复用后仍走确定性合成，但来源标记为 memory（不覆盖）
        state["sql_source"] = "semantic"
    return state


async def sql_hard_guard_node(state: DataAgentState, platform: PlatformClient) -> DataAgentState:
    attempt = state["sql_attempts"][-1]
    resolved = state.get("resolved_intent") or {}
    tr = resolved.get("time_range") or {}
    result = await platform.validate_sql(
        run_id=state["run_id"],
        user_id=state["user_id"],
        question=state["question"],
        sql=attempt["sql"],
        purpose=attempt.get("purpose") or "LangGraph SQL hard guard",
        allow_high_risk=False,
        intent=resolved.get("intent"),
        intent_time_range_type=tr.get("type"),
    )
    state["hard_guard_result"] = result
    attempt["hard_guard_result"] = result
    attempt["risk_level"] = result.get("riskLevel")

    # 统一门禁三态裁决（分类权威在 Java，Python 只做路由）
    verdict = str(result.get("verdict") or "").upper()
    if verdict == "PASS":
        state["hard_guard_feedback"] = "PASS"
        return state
    if verdict == "APPROVAL_NEEDED":
        state["hard_guard_feedback"] = "WAITING_APPROVAL"
        state["approval_status"] = "waiting"
        state["approval_reason"] = _format_guard_feedback(result)
        return state

    # RETRYABLE
    feedback = _format_guard_feedback(result)
    state["hard_guard_feedback"] = feedback
    state["sql_retry_count"] = int(state.get("sql_retry_count", 0)) + 1
    attempt["error"] = feedback
    attempt["success"] = False
    errors = state.setdefault("errors", [])
    errors.append(feedback)
    return state


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
    # SQL_VALIDATE 已删除：EXECUTE 直接承担执行成败判定与重试计数
    if result.get("success"):
        state["execution_feedback"] = "PASS"
    else:
        feedback = _format_execution_feedback(result)
        state["execution_feedback"] = feedback
        state["sql_retry_count"] = int(state.get("sql_retry_count", 0)) + 1
        errors = state.setdefault("errors", [])
        errors.append(feedback)
    return state


def _format_guard_feedback(result: dict) -> str:
    error_code = result.get("code") or result.get("errorCode") or "SQL_HARD_GUARD_FAILED"
    reason = result.get("reason") or "SQL hard guard failed"
    suggestion = result.get("suggestion") or "Regenerate SQL."
    return f"{error_code}: {reason}. Suggestion: {suggestion}"


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


async def _memory_write_hook(state: DataAgentState) -> None:
    """写钩子：仅全链路成功的语义路径沉淀新条目（sql_source=semantic）。命中 run 走 record_hit 独立路径。"""
    if memory is None or not settings.memory_enabled:
        return
    if state.get("sql_source") != "semantic":
        return
    query_result = state.get("query_result") or {}
    if not query_result.get("success"):
        return
    dq = state.get("dq_feedback")
    if dq not in (None, "PASS") and not str(dq or "").startswith("WARNING"):
        return
    intent = state.get("resolved_intent")
    if not intent:
        return
    try:  # 记忆失败不打断主链路
        codes = [str(m) for m in (intent.get("metrics") or [])]
        await memory.upsert(
            normalize_question(state["question"]),
            intent,
            codes,
            compute_resolver_hash(),
            namespace=state.get("memory_namespace", "default"),
        )
    except Exception as exc:  # noqa: BLE001 - 记忆失败不打断主链路
        logger.warning("memory write hook failed: %s", exc)


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
    await _memory_write_hook(state)
    return state
