from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from app.clients.token_meter import meter
from app.eval.comparator import SpecScore, aggregate_scores, compare_spec
from app.eval.metrics import contains_all, required_fields_present
from app.graph import graph_builder
from app.graph.graph_builder import run_chatbi_graph
from app.settings import settings

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES = Path(__file__).with_name("cases.yaml")
DEFAULT_REPORT = ROOT / "docs" / "eval-report.md"
DEFAULT_REPORT_DIR = ROOT / "docs" / "eval-reports"

LLM_MODES = ("mock", "record", "replay", "real")
PLATFORM_MODES = ("mock", "real")
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def load_cases(path: Path) -> tuple[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return str(data.get("eval_date") or "2023-10-14"), list(data.get("cases") or [])


def apply_run_config(llm: str | None, platform: str | None, cassette: str | None,
                    memory: str | None = None) -> dict[str, str]:
    """把 --llm / --platform / --memory 落到 settings，返回自描述运行配置。"""
    if llm is not None:
        settings.eval_llm_mode = llm
    if platform is not None:
        settings.platform_calls_enabled = platform == "real"
    platform_real = settings.platform_calls_enabled
    memory_on = (memory or "off").lower() in ("on", "1", "true")
    settings.memory_enabled = memory_on

    if settings.eval_llm_mode == "record" and platform_real:
        raise SystemExit("illegal combination: --llm record requires platform=mock")
    if settings.eval_llm_mode == "replay" and cassette:
        settings.eval_llm_cassette = cassette
    settings.trace_callback_enabled = platform_real

    return {
        "llm": settings.eval_llm_mode,
        "platform": "real" if platform_real else "mock",
        "model": settings.ai_model,
        "eval_date": "",
        "cassette": settings.eval_llm_cassette if settings.eval_llm_mode in ("record", "replay") else "-",
        "memory": "on" if memory_on else "off",
    }


def report_json_path(eval_date: str, run_config: dict[str, str]) -> Path:
    return DEFAULT_REPORT_DIR / f"eval-{run_config['llm']}-{run_config['platform']}-{eval_date}.json"


async def run_case(case: dict[str, Any], llm: str, platform: str, eval_date: str) -> dict[str, Any]:
    if platform == "real":
        return await run_real_case(case, eval_date)
    return await run_graph_case(case, eval_date)


async def run_cases(cases: list[dict[str, Any]], llm: str, platform: str, eval_date: str) -> list[dict[str, Any]]:
    """逐用例隔离执行：环境性异常标 ERROR，不中断整场评测。"""
    results: list[dict[str, Any]] = []
    by_id = {c["id"]: c for c in cases}
    for case in cases:
        try:
            before = meter.snapshot()
            is_memory_case = bool(case.get("repeat_of") or case.get("memory_setup"))
            if is_memory_case and not settings.memory_enabled:
                results.append({"id": case["id"], "type": case.get("type", "memory"),
                                "passed": True, "reason": "SKIPPED (memory off)", "status": "SUCCESS",
                                "retry_count": 0, "latency_ms": 0, "sql_source": None,
                                "spec_score": None, "memory_hit": False, "tokens": 0})
                continue
            if case.get("repeat_of"):
                results.append(await run_repeat_pair(by_id[case["repeat_of"]], case, platform, eval_date))
            elif case.get("memory_setup"):
                results.append(await run_counterexample(case, platform, eval_date))
            else:
                results.append(await run_case(case, llm, platform, eval_date))
            after = meter.snapshot()
            results[-1]["tokens"] = after["total_tokens"] - before["total_tokens"]
        except Exception as exc:  # noqa: BLE001 - environment failure isolation
            results.append(error_result(case, exc))
    return results


def _experiment_memory_path() -> str:
    """实验记忆路径：lance 后端 + embedding 可用 → 临时目录（不碰真实 memory.lance）；否则 :memory:。"""
    from app.memory.embeddings import get_embedding_provider
    if getattr(settings, "memory_store_backend", "sqlite") == "lance" and get_embedding_provider().available():
        return tempfile.mkdtemp(prefix="eval-memory-")
    return ":memory:"


def _embedding_available() -> bool:
    from app.memory.embeddings import get_embedding_provider
    return get_embedding_provider().available()


async def _close_memory() -> None:
    """关闭实验内建的内存记忆 store，避免 aiosqlite 连接残留导致进程不退出。"""
    from app.graph import nodes
    if nodes.memory is not None:
        try:
            await nodes.memory.close()
        except Exception:  # noqa: BLE001, S110 - 关闭失败静默即可
            pass
        nodes.memory = None


async def _compute_synonym_bands(questions: list[str], namespace: str) -> dict[str, str]:
    """运行时 band 分层（零偏差承诺）：对每条同义问题用【与线上同一实现】的检索器 search 取 top-1 band。

    与 nodes.py 同一工厂/同一判定（含 metrics_consistent + catalog + acceptable 复检），
    不内联重写打分（修复 eval-metrics review P1）。embedding 不可用 → 检索器内部降级 difflib。
    """
    from app.graph import nodes
    from app.memory.embeddings import get_embedding_provider
    from app.memory.retriever import build_retriever, hit_allowed

    if nodes.memory is None:
        return {q: "miss" for q in questions}
    # 与运行时同源的 catalog（mock 平台即本地 metric_catalog.json）
    catalog: list[dict] = []
    try:
        import json as _json
        catalog = _json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001, S110 - catalog 读取失败则不额外校验
        pass
    retriever = build_retriever(nodes.memory, get_embedding_provider())
    bands: dict[str, str] = {}
    for q in questions:
        try:
            hits = await retriever.search(q, namespace=namespace)
            if not hits:
                bands[q] = "miss"
                continue
            band = hits[0].band
            # 零偏差：band=hit 也须过运行时四重判定（catalog/metrics/acceptable），否则标 hit_rejected
            if band == "hit" and catalog and not hit_allowed(q, hits[0].entry, catalog):
                band = "hit_rejected"
            bands[q] = band
        except Exception:  # noqa: BLE001 - 检索失败按 miss（不污染实验）
            bands[q] = "miss"
    return bands


async def run_synonym_experiment(synonym_cases: list[dict], platform: str, memory_on: bool,
                                 eval_date: str) -> dict:
    """同义集实验（自包含，进程内跑图 + runner 本地记忆 store）：
    组 A（无记忆基线）vs 组 B（有记忆：先沉淀 source cases 再跑同义集）。
    按运行时 band 分层报告（hit/inject/miss），inject 子集 < 8 显式标注样本不足。"""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.eval.comparator import compare_spec
    from app.graph.graph_builder import init_memory, run_chatbi_graph

    graph_builder.init_graph(InMemorySaver())
    source_by_id = {}
    if memory_on:
        _d, golden = load_cases(DEFAULT_CASES)
        for c in golden:
            if c.get("golden_spec"):
                source_by_id[c["id"]] = c

    results: list[dict] = []

    # 组 A：memory off，空记忆跑同义集（纯 LLM 基线）
    settings.memory_enabled = False
    for s in synonym_cases:
        state = await run_chatbi_graph({
            "run_id": f"synA_{s['id']}", "user_id": "eval", "question": s["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
        score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
        a_ok = bool(score and score.core_ok)
        results.append({"id": s["id"], "question": s["question"], "a_l1": a_ok,
                        "a_intent": state.get("resolved_intent")})

    # 组 B：memory on，先沉淀 source cases（写路径参与），再跑同义集
    degraded = memory_on and getattr(settings, "memory_store_backend", "sqlite") == "lance" \
        and not _embedding_available()
    if memory_on:
        settings.memory_enabled = True
        await init_memory(_experiment_memory_path())  # 实验自包含，不碰磁盘记忆
        # 沉淀：跑 source cases 的语义路径（写钩子写入 nodes.memory）
        for s in synonym_cases:
            src = source_by_id.get(s.get("source_case"))
            if src is None:
                continue
            await run_chatbi_graph({
                "run_id": f"seed_{src['id']}", "user_id": "eval", "question": src["question"],
                "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
                "warnings": [], "errors": []})
        # 运行时 band 分层（沉淀后，对每条同义问题真实 retriever.search 取 top-1）
        bands = await _compute_synonym_bands([s["question"] for s in synonym_cases],
                                             settings.memory_namespace)
        for r in results:
            r["band"] = bands[r["question"]]
        for s in synonym_cases:
            state = await run_chatbi_graph({
                "run_id": f"synB_{s['id']}", "user_id": "eval", "question": s["question"],
                "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
                "warnings": [], "errors": []})
            score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
            r = next(x for x in results if x["id"] == s["id"])
            r["b_l1"] = bool(score and score.core_ok)
            r["b_intent"] = state.get("resolved_intent")
            r["sql_source"] = state.get("sql_source")
    else:
        for r in results:
            r["band"] = "miss"  # memory off：无记忆，全 miss
            r["b_l1"] = r["a_l1"]

    n = {"hit": sum(1 for r in results if r["band"] == "hit"),
         "inject": sum(1 for r in results if r["band"] == "inject"),
         "miss": sum(1 for r in results if r["band"] == "miss")}
    inject_sub = [r for r in results if r["band"] == "inject"]
    a_ok = sum(1 for r in results if r["a_l1"])
    inject_b_ok = sum(1 for r in inject_sub if r.get("b_l1"))
    inject_a_ok = sum(1 for r in inject_sub if r["a_l1"])
    inject_n = len(inject_sub)
    sample_warn = inject_n < 8
    await _close_memory()
    return {
        "degraded": degraded,
        "n_band": n, "synonym_total": len(results),
        "group_a_l1": a_ok / len(results) if results else 0,
        "inject_n": inject_n,
        "inject_a_l1": inject_a_ok / inject_n if inject_n else 0,
        "inject_b_l1": inject_b_ok / inject_n if inject_n else 0,
        "inject_b_gain": (inject_b_ok - inject_a_ok) / inject_n if inject_n else 0,
        "sample_warning": sample_warn,
        "per_item": results,
    }


async def run_cold_hot_experiment(synonym_cases: list[dict], platform: str,
                              eval_date: str) -> dict:
    """冷热启动实验（3.3，检索侧，与注入实验区分）：
    冷 = 空记忆（纯 LLM 基线）；热 = 直接 seed 预置 golden intent 进 eval namespace
    （消除写路径方差，只测检索侧收益）。按运行时 band 分层报告延迟/L1 差。"""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.eval.comparator import compare_spec
    from app.graph.graph_builder import init_memory, run_chatbi_graph

    graph_builder.init_graph(InMemorySaver())
    _d, golden = load_cases(DEFAULT_CASES)
    source_by_id = {c["id"]: c for c in golden if c.get("golden_spec")}

    results: list[dict] = []

    # 冷：空记忆，纯 LLM 基线（记忆 off，同义集逐条）
    settings.memory_enabled = False
    for s in synonym_cases:
        start = time.perf_counter()
        state = await run_chatbi_graph({
            "run_id": f"cold_{s['id']}", "user_id": "eval", "question": s["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
        latency = int((time.perf_counter() - start) * 1000)
        score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
        results.append({"id": s["id"], "question": s["question"],
                        "cold_l1": bool(score and score.core_ok),
                        "cold_latency_ms": latency})

    # 热：seed 预置（直接写 store，不走图/写钩子 → 消除写路径方差）
    degraded = getattr(settings, "memory_store_backend", "sqlite") == "lance" and not _embedding_available()
    settings.memory_enabled = True
    await init_memory(_experiment_memory_path())
    for s in synonym_cases:
        src = source_by_id.get(s.get("source_case"))
        if src is None:
            continue
        await _seed_memory(
            question=src["question"],
            intent=src["golden_spec"],
            metric_codes=[str(m) for m in (src.get("golden_spec") or {}).get("metrics", [])],
            namespace=settings.memory_namespace, platform="mock")
    # 运行时 band 分层（与注入实验一致：对每条同义问题真实 retriever top-1）
    bands = await _compute_synonym_bands([s["question"] for s in synonym_cases],
                                         settings.memory_namespace)
    for s in synonym_cases:
        start = time.perf_counter()
        state = await run_chatbi_graph({
            "run_id": f"hot_{s['id']}", "user_id": "eval", "question": s["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
        latency = int((time.perf_counter() - start) * 1000)
        score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
        r = next(x for x in results if x["id"] == s["id"])
        r["band"] = bands[s["question"]]
        r["hot_l1"] = bool(score and score.core_ok)
        r["hot_latency_ms"] = latency
        r["sql_source"] = state.get("sql_source")
        r["memory_hit"] = bool(state.get("memory_hit"))

    n = {"hit": sum(1 for r in results if r["band"] == "hit"),
         "inject": sum(1 for r in results if r["band"] == "inject"),
         "miss": sum(1 for r in results if r["band"] == "miss")}
    cold_ok = sum(1 for r in results if r["cold_l1"])
    hot_ok = sum(1 for r in results if r.get("hot_l1"))
    cold_lats = sorted(r["cold_latency_ms"] for r in results)
    hot_lats = sorted(r["hot_latency_ms"] for r in results)
    await _close_memory()
    return {
        "degraded": degraded,
        "n_band": n, "synonym_total": len(results),
        "cold_l1": cold_ok / len(results) if results else 0,
        "hot_l1": hot_ok / len(results) if results else 0,
        "l1_gain": (hot_ok - cold_ok) / len(results) if results else 0,
        "cold_latency_p50": statistics.median(cold_lats) if cold_lats else 0,
        "hot_latency_p50": statistics.median(hot_lats) if hot_lats else 0,
        "hot_hit_count": sum(1 for r in results if r.get("memory_hit")),
        "per_item": results,
    }


async def run_repeat_pair(base_case: dict[str, Any], meta: dict[str, Any],
                          platform: str, eval_date: str) -> dict[str, Any]:
    """重复问题对：同一 question 连续跑两遍，断言第二遍命中且 intent 逐字段一致（口径=两遍都成功）。

    直通收益（3.1）：逐遍记录延迟与用例总 token，返回 r1 vs r2 差值——
    命中路径只消除解析阶段 LLM（AnswerAgent 仍调 LLM），收益 = 用例总 token 差/延迟差（≈ 解析阶段消除）。
    """
    start = time.perf_counter()
    before = meter.snapshot()
    r1 = await run_case(base_case, "real", platform, eval_date)
    after = meter.snapshot()
    r1_tokens = after["total_tokens"] - before["total_tokens"]
    r1_latency_ms = int(r1.get("latency_ms", 0))
    before = meter.snapshot()
    r2 = await run_case(base_case, "real", platform, eval_date)
    after = meter.snapshot()
    r2_tokens = after["total_tokens"] - before["total_tokens"]
    r2_latency_ms = int(r2.get("latency_ms", 0))
    latency_ms = int((time.perf_counter() - start) * 1000)
    both_ok = r1["passed"] and r2["passed"] and r1["status"] != "ERROR" and r2["status"] != "ERROR"
    hit = bool(r2.get("memory_hit"))
    same = (r1.get("resolved_intent") or {}) == (r2.get("resolved_intent") or {})
    passed = both_ok and hit and same
    reason = "PASS"
    if not both_ok:
        reason = f"repeat pair: r1={r1['reason']} | r2={r2['reason']}"
    elif not hit:
        reason = "repeat pair: second run did not hit memory"
    elif not same:
        reason = "repeat pair: resolved_intent differs between runs"
    return {
        "id": meta["id"], "type": meta.get("type", "memory"),
        "passed": passed, "reason": reason, "latency_ms": latency_ms,
        "status": "SUCCESS" if passed else "FAIL", "retry_count": 0,
        "sql_source": r2.get("sql_source"), "spec_score": r2.get("spec_score"),
        "resolved_intent": r2.get("resolved_intent"),
        "memory_hit": hit, "memory_band": r2.get("memory_band"),
        # 直通收益计量（3.1）
        "r1_latency_ms": r1_latency_ms, "r2_latency_ms": r2_latency_ms,
        "latency_delta_ms": r1_latency_ms - r2_latency_ms,
        "r1_tokens": r1_tokens, "r2_tokens": r2_tokens,
        "token_delta": r1_tokens - r2_tokens,
        "direct_hit": hit,
    }


async def _seed_memory(question: str, intent: dict, metric_codes: list[str],
                        namespace: str, platform: str) -> bool:
    """预置记忆：real 走服务器 API（POST /internal/memory/seed），mock 写本地 store。"""
    from app.graph import nodes
    from app.memory.retriever import normalize_question
    from app.memory.store import compute_resolver_hash

    try:
        if platform == "real":
            async with httpx.AsyncClient(timeout=30) as client:
                # 记忆控制端点在 agent-engine（localhost:8090），与 Spring 平台端口不同
                resp = await client.post(
                    "http://localhost:8090/internal/memory/seed",
                    headers={"X-Internal-Token": settings.internal_api_token},
                    json={"namespace": namespace, "question": question,
                          "intent": intent, "metric_codes": metric_codes})
                resp.raise_for_status()
        else:
            if nodes.memory is None:
                print(f"[eval] seed skipped: memory not initialized (q={question})")
                return False
            eid = await nodes.memory.upsert(normalize_question(question), intent, metric_codes,
                                            compute_resolver_hash(), namespace=namespace)
            if eid is not None and eid < 0:
                print(f"[eval] seed skipped: embedding failed (q={question})")
                return False
        return True
    except Exception as exc:  # noqa: BLE001 - 预置失败不再静默
        print(f"[eval] seed failed (q={question}): {type(exc).__name__}: {exc}")
        return False


async def run_counterexample(case: dict[str, Any], platform: str, eval_date: str) -> dict[str, Any]:
    """毒化变体反例：预置"问题文本与 intent 指标不一致"的毒条目，查询同文本（相似度 1.0 → 直通候选）
    断言 metrics 一致性校验拦截（band != hit）——同时验证 seed 毒化防护与 metrics 校验路径。"""
    start = time.perf_counter()
    setup = case.get("memory_setup") or {}
    seed_ok = await _seed_memory(
        question=str(setup.get("question") or case["question"]),
        intent=setup.get("intent") or {}, metric_codes=setup.get("metric_codes") or [],
        namespace=settings.memory_namespace, platform=platform)
    if not seed_ok:
        return {**error_result(case, RuntimeError("memory seeding failed")), "memory_band": None}
    r = await run_case(case, "real", platform, eval_date)
    latency_ms = int((time.perf_counter() - start) * 1000)
    r["id"] = case["id"]
    r["type"] = case.get("type", "memory")
    r["latency_ms"] = latency_ms
    # 毒化变体断言：同文本相似度 1.0 应进直通候选，但 metrics 一致性校验必须拦截 → band != hit
    not_hit = not bool(r.get("memory_hit"))
    r["passed"] = r["passed"] and not_hit
    if not not_hit:
        r["reason"] = "counterexample: poison entry unexpectedly passed metrics check (hit)"
    return r
    r = await run_case(case, "real", platform, eval_date)
    latency_ms = int((time.perf_counter() - start) * 1000)
    r["id"] = case["id"]
    r["type"] = case.get("type", "memory")
    r["latency_ms"] = latency_ms
    # 反例断言：不得命中（band != hit）
    not_hit = not bool(r.get("memory_hit"))
    r["passed"] = r["passed"] and not_hit
    if not not_hit:
        r["reason"] = "counterexample: unexpectedly hit memory"
    return r


def error_result(case: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "id": case["id"],
        "type": case.get("type", ""),
        "passed": False,
        "reason": f"ERROR: {type(exc).__name__}: {exc}",
        "latency_ms": 0,
        "status": "ERROR",
        "retry_count": 0,
        "sql_source": None,
        "spec_score": None,
        "error": True,
        "tokens": 0,
    }


async def run_graph_case(case: dict[str, Any], eval_date: str) -> dict[str, Any]:
    """mock/replay：跑真实图（LLM 由 settings.eval_llm_mode 控制），平台走 mock。"""
    start = time.perf_counter()
    original_validate_sql = graph_builder.platform.validate_sql
    original_execute_sql = graph_builder.platform.execute_sql
    original_check_dq = graph_builder.platform.check_sql_result_dq

    if int(case.get("mock_guard_failures", 0)) > 0:
        graph_builder.platform.validate_sql = _mock_guard(case)
    if case.get("mock_guard_verdict"):
        graph_builder.platform.validate_sql = _mock_verdict(case["mock_guard_verdict"])
    if case.get("mock_high_risk"):
        graph_builder.platform.validate_sql = _mock_high_risk
    if int(case.get("mock_dq_failures", 0)) > 0 or case.get("mock_dq_warning"):
        graph_builder.platform.check_sql_result_dq = _mock_dq(case)

    try:
        state = await run_chatbi_graph(
            {
                "run_id": f"eval_{case['id']}",
                "user_id": "eval",
                "question": case["question"],
                "graph_mode": "chatbi",
                "memory_namespace": settings.memory_namespace,
                "warnings": [],
                "errors": [],
            }
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        passed, reason = evaluate_case(case, state)
        score = compare_spec(state.get("resolved_intent"), case.get("golden_spec"), eval_date)
    finally:
        graph_builder.platform.validate_sql = original_validate_sql
        graph_builder.platform.execute_sql = original_execute_sql
        graph_builder.platform.check_sql_result_dq = original_check_dq

    return {
        "id": case["id"],
        "type": case["type"],
        "passed": passed,
        "reason": reason,
        "latency_ms": latency_ms,
        "status": "WAITING_APPROVAL" if state.get("approval_status") == "waiting" else "SUCCESS",
        "retry_count": int(state.get("sql_retry_count", 0)),
        "sql_source": state.get("sql_source"),
        "spec_score": _score_dict(score),
        "resolved_intent": state.get("resolved_intent"),
        "memory_hit": bool(state.get("memory_hit")),
        "memory_band": state.get("memory_band"),
    }


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS
    return False


async def _get_analyze(client: httpx.AsyncClient, question: str) -> httpx.Response:
    url = f"{settings.platform_base_url.rstrip('/')}/api/agent/analyze"
    params = {"userId": "eval", "message": question, "nocache": "true", "includeDebug": "true",
              "memoryNamespace": settings.memory_namespace}
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response
        except (httpx.HTTPStatusError, httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt == 0 and _is_retryable(exc):
                await asyncio.sleep(2)
                continue
            raise
    raise last_exc  # pragma: no cover


async def _approve_and_get(client: httpx.AsyncClient, run_id: str) -> dict[str, Any]:
    """自动放行：调用 Spring 审批接口恢复执行，返回最终报告。失败抛异常 → 由调用方按 ERROR 处理。"""
    url = f"{settings.platform_base_url.rstrip('/')}/api/agent/runs/{run_id}/approval"
    response = await client.post(url, json={"approved": True})
    response.raise_for_status()
    return response.json()


async def run_real_case(case: dict[str, Any], eval_date: str) -> dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx is required for platform=real")
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        response = await _get_analyze(client, case["question"])
        payload = response.json()
        debug = payload.get("debug") or {}
        auto_released = False
        # 非 risk 用例被门禁拦截（WAITING_APPROVAL）→ 自动放行补跑，验证审批后完整链路
        if payload.get("status") == "WAITING_APPROVAL" and case.get("expected_status") != "WAITING_APPROVAL":
            run_id = payload.get("runId") or payload.get("run_id")
            approved = await _approve_and_get(client, run_id)  # 失败抛异常 → run_cases 标 ERROR
            payload = approved
            debug = payload.get("debug") or debug  # 保留原 debug（resolvedIntent 用于 L1~L4 评分）
            auto_released = True
    # Spring /api/agent/analyze 直接返回 AnalysisReport（无 finalReport 包装）
    final_report = payload.get("finalReport") or payload.get("final_report") or payload
    state = {
        "route": "complex",
        "approval_status": "waiting" if payload.get("status") == "WAITING_APPROVAL" else None,
        "sql_attempts": [{"sql": final_report.get("sql", "")}],
        "sql_retry_count": debug.get("sqlRetryCount") or payload.get("sqlRetryCount") or 0,
        "final_report": final_report,
        "resolved_intent": debug.get("resolvedIntent") or payload.get("resolvedIntent") or payload.get("resolved_intent"),
        "sql_source": debug.get("sqlSource") or payload.get("sqlSource"),
        "memory_hit": debug.get("memoryHit") or payload.get("memoryHit"),
        "memory_band": debug.get("memoryBand") or payload.get("memoryBand"),
    }
    latency_ms = int((time.perf_counter() - start) * 1000)
    passed, reason = evaluate_case(case, state)
    score = compare_spec(state.get("resolved_intent"), case.get("golden_spec"), eval_date)
    return {
        "id": case["id"],
        "type": case["type"],
        "passed": passed,
        "reason": reason,
        "latency_ms": latency_ms,
        "status": "WAITING_APPROVAL" if state.get("approval_status") == "waiting" else "SUCCESS",
        "retry_count": int(state.get("sql_retry_count", 0)),
        "sql_source": state.get("sql_source"),
        "spec_score": _score_dict(score),
        "auto_released": auto_released,
        "resolved_intent": state.get("resolved_intent"),
        "memory_hit": bool(state.get("memory_hit")),
        "memory_band": state.get("memory_band"),
    }


def _score_dict(score: SpecScore | None) -> dict[str, Any] | None:
    if score is None:
        return None
    return {
        "matched": score.matched,
        "core_ok": score.core_ok,
        "field_hits": score.field_hits,
        "field_total": score.field_total,
        "fields": score.fields,
    }


def evaluate_case(case: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    if (expected := case.get("expected_route")) and state.get("route") != expected:
        return False, f"route={state.get('route')} expected={expected}"

    status = "WAITING_APPROVAL" if state.get("approval_status") == "waiting" else "SUCCESS"
    if (expected_status := case.get("expected_status")) and status != expected_status:
        return False, f"status={status} expected={expected_status}"

    if (expected_sql := case.get("expected_sql_contains")) and not contains_all(
        " ".join(str(attempt.get("sql", "")) for attempt in (state.get("sql_attempts") or [])),
        expected_sql,
    ):
        return False, "generated SQL missing expected fragments"

    if (expected_fields := case.get("expected_report_fields")) and not required_fields_present(
        state.get("final_report") or {}, expected_fields
    ):
        return False, "final report missing required fields"

    if (expected_keywords := case.get("expected_report_keywords")) and not contains_all(
        json.dumps(state.get("final_report") or {}, ensure_ascii=False), expected_keywords
    ):
        return False, "final report missing expected keywords"

    if "expected_sql_retry_count" in case and int(state.get("sql_retry_count", 0)) != int(
        case["expected_sql_retry_count"]
    ):
        return False, (
            f"sql_retry_count={state.get('sql_retry_count')} expected={case['expected_sql_retry_count']}"
        )

    return True, "PASS"


# ---------------------------------------------------------------------------
# Mock platform behaviors
# ---------------------------------------------------------------------------
def _mock_guard(case: dict[str, Any]):
    failures = int(case.get("mock_guard_failures", 0))

    async def validate_sql(*args, **kwargs):
        nonlocal failures
        if failures > 0:
            failures -= 1
            return {
                "verdict": "RETRYABLE",
                "code": "SQL_NOT_SELECT",
                "reason": "Only SELECT statements are allowed.",
                "suggestion": "Rewrite as SELECT.",
                "riskLevel": "HIGH",
                "accessedTables": [],
            }
        return {
            "verdict": "PASS",
            "code": None,
            "reason": None,
            "suggestion": None,
            "riskLevel": "LOW",
            "accessedTables": ["metric_daily"],
        }

    return validate_sql


def _mock_verdict(verdict: str):
    """按指定三态注入门禁响应（mock 三态注入，配合门禁行为用例）。"""
    responses = {
        "PASS": {
            "verdict": "PASS", "code": None, "reason": None, "suggestion": None,
            "riskLevel": "LOW", "accessedTables": ["metric_daily"],
        },
        "RETRYABLE": {
            "verdict": "RETRYABLE", "code": "SQL_RULE_WARNING",
            "reason": "Aggregate query lacks required event_type filter.",
            "suggestion": "Add event_type filter.", "riskLevel": "MEDIUM",
            "accessedTables": ["metric_daily"],
        },
        "APPROVAL_NEEDED": {
            "verdict": "APPROVAL_NEEDED", "code": "SQL_FULL_SCAN",
            "reason": "Full table scan on fact table (user_behavior_fact).",
            "suggestion": "Add WHERE conditions or approve via HITL.",
            "riskLevel": "HIGH", "accessedTables": ["user_behavior_fact"],
        },
    }
    payload = responses.get(verdict, responses["RETRYABLE"])

    async def validate_sql(*args, **kwargs):
        return dict(payload)

    return validate_sql


async def _mock_high_risk(*args, **kwargs):
    return {
        "verdict": "APPROVAL_NEEDED",
        "code": "DETAIL_QUERY_WITHOUT_LIMIT",
        "reason": "Detail table queries must include LIMIT.",
        "suggestion": "Approve only if the detail query is necessary.",
        "riskLevel": "HIGH",
        "accessedTables": ["play_detail"],
    }


def _mock_dq(case: dict[str, Any]):
    failures = int(case.get("mock_dq_failures", 0))
    warning = bool(case.get("mock_dq_warning"))

    async def check_sql_result_dq(*args, **kwargs):
        nonlocal failures
        if failures > 0:
            failures -= 1
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
            "warnings": ["Result was truncated; answer should mention partial data."]
            if warning
            else [],
        }

    return check_sql_result_dq


# ---------------------------------------------------------------------------
# Aggregation & report
# ---------------------------------------------------------------------------
def _percent(part: int, total: int) -> float:
    return (part / total) if total else 0.0


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    evaluated = [r for r in results if r.get("status") != "ERROR"]
    errors = [r for r in results if r.get("status") == "ERROR"]
    passed = sum(1 for r in evaluated if r["passed"])
    retried = [r for r in results if r["retry_count"] > 0]
    auto_fix = sum(1 for r in retried if r["passed"])
    risk = [r for r in results if r["type"] == "risk"]
    risk_ok = sum(1 for r in risk if r["status"] == "WAITING_APPROVAL")
    auto_released = [r for r in evaluated if r.get("auto_released")]
    unexpected_intercepts = [r for r in evaluated if r.get("auto_released") and not r["passed"]]

    scores = [
        SpecScore(
            matched=r["spec_score"]["matched"],
            core_ok=r["spec_score"]["core_ok"],
            field_hits=r["spec_score"]["field_hits"],
            field_total=r["spec_score"]["field_total"],
            fields=r["spec_score"]["fields"],
        )
        for r in results
        if r["spec_score"] is not None
    ]
    layer = aggregate_scores(scores)

    latencies = sorted(r["latency_ms"] for r in evaluated)
    return {
        "total": total,
        "evaluated": len(evaluated),
        "error_count": len(errors),
        "passed": passed,
        "end_to_end": _percent(passed, len(evaluated)),
        "auto_fix": _percent(auto_fix, len(retried)),
        "auto_fix_total": len(retried),
        "risk_interception": _percent(risk_ok, len(risk)),
        "risk_total": len(risk),
        "auto_released": len(auto_released),
        "auto_released_ratio": _percent(len(auto_released), len(evaluated)),
        "unexpected_intercepts": len(unexpected_intercepts),
        "memory_hit": sum(1 for r in evaluated if r.get("memory_hit")),
        "memory_hit_rate": _percent(sum(1 for r in evaluated if r.get("memory_hit")), len(evaluated)),
        "memory_inject": sum(1 for r in evaluated if r.get("memory_band") == "inject"),
        "memory_inject_rate": _percent(sum(1 for r in evaluated if r.get("memory_band") == "inject"), len(evaluated)),
        "tokens_total": sum(r.get("tokens", 0) for r in evaluated),
        "tokens_hit_avg": _avg_tokens([r for r in evaluated if r.get("memory_hit")]),
        "tokens_miss_avg": _avg_tokens([r for r in evaluated if not r.get("memory_hit")]),
        "repeat_pairs": sum(1 for r in evaluated if "r1_tokens" in r),
        "direct_hit_pairs": sum(1 for r in evaluated if r.get("direct_hit") and "r1_tokens" in r),
        "direct_hit_avg_token_delta": _avg_key(
            [r for r in evaluated if r.get("direct_hit") and "r1_tokens" in r], "token_delta"),
        "direct_hit_avg_latency_delta": _avg_key(
            [r for r in evaluated if r.get("direct_hit") and "r1_tokens" in r], "latency_delta_ms"),
        "judged": len(scores),
        "core_accuracy": layer["core"],
        "core_hits": sum(1 for s in scores if s.core_ok),
        "strict_accuracy": layer["strict"],
        "strict_hits": sum(1 for s in scores if s.matched),
        "avg_field_match": layer["avg_field"],
        "per_field": {name: layer[name] for name in ["intent", "metrics", "dimensions", "time_range", "filters", "ordering"]},
        "latency_p50": statistics.median(latencies) if latencies else 0,
        "latency_p95": _percentile(latencies, 0.95),
    }


def _avg_tokens(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(r.get("tokens", 0) for r in results) / len(results)


def _avg_key(results: list[dict], key: str) -> float:
    if not results:
        return 0.0
    return sum(r.get(key, 0) for r in results) / len(results)


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_values) else f
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def render_report(results: list[dict[str, Any]], run_config: dict[str, str], eval_date: str) -> str:
    agg = aggregate(results)
    lines = [
        "# DataAgent Evaluation Report",
        "",
        f"- LLM: `{run_config['llm']}` | 平台: `{run_config['platform']}` | 模型: `{run_config['model']}`",
        f"- eval_date: `{eval_date}` | cassette: `{run_config.get('cassette', '-')}`",
        f"- 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Metrics",
        "",
        "| Metric | Score | Detail |",
        "|---|---:|---:|",
        f"| 评测可用性 | {_percent(agg['evaluated'], agg['total']):.0%} | {agg['evaluated']}/{agg['total']} |",
        f"| 端到端成功率 | {agg['end_to_end']:.2%} | {agg['passed']}/{agg['evaluated']} |",
        f"| 口径核心正确率 (L1) | {agg['core_accuracy']:.2%} | {agg['core_hits']}/{agg['judged']} |",
        f"| 严格全字段正确率 (L2) | {agg['strict_accuracy']:.2%} | {agg['strict_hits']}/{agg['judged']} |",
        f"| 平均字段匹配率 (L3) | {agg['avg_field_match']:.2%} | judged={agg['judged']} |",
        f"| 自动修复成功率 | {agg['auto_fix']:.2%} | {agg['auto_fix_total']} cases retried |",
        f"| 高风险拦截率 | {agg['risk_interception']:.2%} | {agg['risk_total']} cases |",
        f"| 自动放行（auto_released） | {agg['auto_released_ratio']:.2%} | {agg['auto_released']}/{agg['evaluated']}（非 risk 用例被拦截后自动放行） |",
        f"| 记忆命中率（memory_hit） | {agg['memory_hit_rate']:.2%} | {agg['memory_hit']}/{agg['evaluated']} |",
        f"| 记忆注入率（memory_inject） | {agg['memory_inject_rate']:.2%} | {agg['memory_inject']}/{agg['evaluated']} |",
        f"| Token 总消耗 | {agg['tokens_total']} | 命中均值 {agg['tokens_hit_avg']:.0f} / 未命中均值 {agg['tokens_miss_avg']:.0f} |",
        f"| 直通收益（重复对） | token 差均值 {agg['direct_hit_avg_token_delta']:.0f} / 延迟差均值 {agg['direct_hit_avg_latency_delta']:.0f}ms | {agg['direct_hit_pairs']}/{agg['repeat_pairs']} 对命中直通（≈ 解析阶段消除） |",
        f"| 意外拦截数 | {agg['unexpected_intercepts']} | 自动放行后仍失败的用例（门禁过度拦截信号） |",
        f"| 延迟 p50 / p95 | {agg['latency_p50']}ms / {agg['latency_p95']:.0f}ms | - |",
        "",
        "## 分项正确率 (L4)",
        "",
        "| Field | Accuracy |",
        "|---|---:|",
    ]
    for name, value in agg["per_field"].items():
        lines.append(f"| {name} | {value:.2%} |")
    lines.extend(["", "## Cases", "", "| Case | Type | Result | Status | Source | Retry | Latency | Reason |", "|---|---|---|---|---|---:|---:|---|"])
    for result in results:
        outcome = "ERROR" if result["status"] == "ERROR" else ("PASS" if result["passed"] else "FAIL")
        lines.append(
            f"| {result['id']} | {result['type']} | {outcome} | {result['status']} | "
            f"{result.get('sql_source') or '-'} | {result['retry_count']} | {result['latency_ms']}ms | {result['reason']} |"
        )
    errors = [r for r in results if r.get("status") == "ERROR"]
    if errors:
        lines.extend(["", "## ERROR 用例（环境性失败，不计入 judged）", "", "| Case | Reason |", "|---|---|"])
        for result in errors:
            lines.append(f"| {result['id']} | {result['reason']} |")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# A/B compare
# ---------------------------------------------------------------------------
def compare_reports(report_a: dict[str, Any], report_b: dict[str, Any]) -> str:
    cfg_a = report_a.get("config") or {}
    cfg_b = report_b.get("config") or {}
    if cfg_a and cfg_b:
        diff = {
            key: (cfg_a.get(key), cfg_b.get(key))
            for key in ("llm", "platform", "eval_date", "model")
            if cfg_a.get(key) != cfg_b.get(key)
        }
        if diff:
            lines = ["# Eval A/B Compare", "", "**拒绝对比：运行配置不一致**", ""]
            lines.extend(f"- {key}: A=`{va[0]}` B=`{va[1]}`" for key, va in diff.items())
            return "\n".join(lines)

    a = report_a.get("metrics", report_a)
    b = report_b.get("metrics", report_b)
    lines = ["# Eval A/B Compare", "", "| Metric | A | B | Δ |", "|---|---:|---:|---:|"]
    ratio_keys = [
        "end_to_end", "core_accuracy", "strict_accuracy", "avg_field_match",
        "auto_fix", "risk_interception",
    ]
    for key in ratio_keys:
        av = a.get(key, 0.0)
        bv = b.get(key, 0.0)
        lines.append(f"| {key} | {av:.2%} | {bv:.2%} | {bv - av:+.2%} |")
    for key in ["latency_p50"]:
        av = a.get(key, 0.0)
        bv = b.get(key, 0.0)
        lines.append(f"| {key} | {av}ms | {bv}ms | {bv - av:+.0f}ms |")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run DataAgent evaluation cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--llm",
        choices=LLM_MODES,
        default=None,
        help="LLM source: mock|record|replay|real (default: EVAL_LLM_MODE)",
    )
    parser.add_argument(
        "--platform",
        choices=PLATFORM_MODES,
        default=None,
        help="platform source: mock|real (default: PLATFORM_CALLS_ENABLED)",
    )
    parser.add_argument("--cassette", default=None)
    parser.add_argument("--memory", choices=["off", "on"], default="off",
                        help="语义记忆开关（默认 off，回归隔离；on 需配合独立记忆库）")
    parser.add_argument("--compare", nargs=2, metavar=("A_JSON", "B_JSON"))
    parser.add_argument("--synonym-cases", type=Path, default=None,
                        help="同义集实验：跑组 A（无记忆）/组 B（有记忆）对比")
    parser.add_argument("--cold-hot", action="store_true", default=False,
                        help="冷热启动实验（需 --synonym-cases）：空记忆 vs seed 预置记忆，测检索侧收益")
    args = parser.parse_args()

    if args.compare:
        a = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        b = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        print(compare_reports(a, b))
        return

    run_config = apply_run_config(args.llm, args.platform, args.cassette, args.memory)
    eval_date, cases = load_cases(args.cases)
    run_config["eval_date"] = eval_date

    if args.synonym_cases:
        _date, syn_cases = load_cases(args.synonym_cases)
        if args.cold_hot:
            exp = await run_cold_hot_experiment(syn_cases, run_config["platform"], eval_date)
            print(f"[cold-hot] N_hit={exp['n_band']['hit']} N_inject={exp['n_band']['inject']} "
                  f"N_miss={exp['n_band']['miss']}")
            print(f"[cold-hot] 冷 L1={exp['cold_l1']:.2%} | 热 L1={exp['hot_l1']:.2%} "
                  f"增益={exp['l1_gain']:+.2%} | 延迟 p50 {exp['cold_latency_p50']}ms → {exp['hot_latency_p50']}ms "
                  f"| 热命中 {exp['hot_hit_count']}/{exp['synonym_total']}")
        else:
            exp = await run_synonym_experiment(syn_cases, run_config["platform"],
                                               settings.memory_enabled, eval_date)
            print(f"[synonym] N_hit={exp['n_band']['hit']} N_inject={exp['n_band']['inject']} "
                  f"N_miss={exp['n_band']['miss']}")
            print(f"[synonym] 组A L1={exp['group_a_l1']:.2%} | inject 子集 B L1={exp['inject_b_l1']:.2%} "
                  f"增益={exp['inject_b_gain']:+.2%}")
            if exp["sample_warning"]:
                print("[synonym] WARNING: inject 子集样本不足(<8)，结论仅方向性")
        import json as _json
        print(_json.dumps(exp, ensure_ascii=False, indent=2))
        return

    from app.graph.checkpoints import create_checkpointer

    db_path = ":memory:" if run_config["platform"] == "mock" else settings.checkpoint_db_path
    checkpointer = await create_checkpointer(db_path)
    graph_builder.init_graph(checkpointer)

    # 记忆隔离：无论 on/off，eval 都用 per-eval namespace（eval-<eval_date>-<start_ts>）
    # —— 即使 --memory off，服务器写钩子也会写；隔离到 eval namespace 可避免污染 default 真实记忆
    import time as _t
    settings.memory_namespace = f"eval-{eval_date}-{int(_t.time())}"
    if settings.memory_enabled:
        memory_db = ":memory:" if run_config["platform"] == "mock" else settings.memory_db_path
        await graph_builder.init_memory(memory_db)
        # 清空 eval namespace（real 走 API / mock 走本地）
        if run_config["platform"] == "real":
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "http://localhost:8090/internal/memory/clear",
                    headers={"X-Internal-Token": settings.internal_api_token},
                    json={"namespace": settings.memory_namespace})
                resp.raise_for_status()
        else:
            from app.graph import nodes as _nodes
            if _nodes.memory is not None:
                await _nodes.memory.clear(settings.memory_namespace)

    results = await run_cases(cases, run_config["llm"], run_config["platform"], eval_date)
    await checkpointer.conn.close()
    from app.graph import nodes
    if nodes.memory is not None:
        try:
            await nodes.memory.close()
        except Exception as exc:  # noqa: BLE001
            print(f"[eval] memory close failed: {exc}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(results, run_config, eval_date), encoding="utf-8")
    json_path = report_json_path(eval_date, run_config)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_report = {
        "config": run_config,
        "eval_date": eval_date,
        "metrics": aggregate(results),
        "cases": results,
    }
    json_path.write_text(json.dumps(json_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.report} and {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
