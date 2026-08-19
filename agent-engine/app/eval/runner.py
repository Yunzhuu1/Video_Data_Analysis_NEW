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
            # R1：L1 通过且含 expected_result → 独立 MySQL 执行合成 SQL 断言结果
            last = results[-1]
            score = last.get("spec_score")
            if last.get("status") != "ERROR" and score and score.get("core_ok") and case.get("expected_result"):
                last["result_check"] = await _check_case_result(case, last)
            else:
                last["result_check"] = None
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


def _real_session_memory_path() -> str:
    """real-session 记忆路径：必须是持久化文件路径（弱验证 close/reopen 需要落盘）。
    lance 后端 + embedding 可用 → 临时 lance 目录；否则临时 sqlite 文件。"""
    from app.memory.embeddings import get_embedding_provider
    d = tempfile.mkdtemp(prefix="real-session-memory-")
    if getattr(settings, "memory_store_backend", "sqlite") == "lance" and get_embedding_provider().available():
        return d
    return str(Path(d) / "memory.sqlite")


def _assert_real_session_valid(llm: str) -> None:
    """real-session 协议前置校验：真实 LLM（real/replay）才可沉淀；mock LLM 直接报错。"""
    if llm == "mock":
        raise SystemExit(
            "--protocol real-session 需要真实 LLM（--llm real 或 replay）；mock LLM 无法产出 resolved_intent，"
            "写入门槛（sql_source=semantic + 执行成功 + DQ PASS/WARNING）永不满足。")


def _real_session_namespace(eval_date: str) -> str:
    """真实路径评测 namespace：real-<eval_date>-<start_ts>，一次评测一个，与 eval-*/default 隔离。"""
    return f"real-{eval_date}-{int(time.time())}"


def _pick_real_sessions(cases: list[dict[str, Any]], n: int = 8) -> list[dict[str, Any]]:
    """从 golden cases 选 n 个代表性问题：覆盖 intent 多样性（aggregate/trend/ranking/detail），
    跳过 memory 专用用例（repeat_of/memory_setup）。"""
    golden = [c for c in cases if c.get("golden_spec") and not (c.get("repeat_of") or c.get("memory_setup"))]
    by_intent: dict[str, list[dict[str, Any]]] = {}
    for c in golden:
        it = (c["golden_spec"] or {}).get("intent", "aggregate")
        by_intent.setdefault(it, []).append(c)
    picked: list[dict[str, Any]] = []
    seen: set[str] = set()
    intents = ["aggregate", "trend", "ranking", "detail"]
    while len(picked) < n:
        added = False
        for it in intents:
            if len(picked) >= n:
                break
            for c in by_intent.get(it, []):
                if c["id"] not in seen:
                    picked.append(c)
                    seen.add(c["id"])
                    added = True
                    break
        if not added:
            break
    return picked[:n]


def _variant_for(case: dict[str, Any], syn_cases: list[dict[str, Any]]) -> str | None:
    """近似问变体：复用同义集 easy 层里 source_case 匹配的条目；无匹配则 None（跳过近似问，仅观测）。
    近似问在本 change 中仅观测（band 任意分层）；若需演示注入收益需离线校验融合分 ≥ inject_t。"""
    for s in syn_cases:
        if s.get("source_case") == case["id"] and s.get("difficulty") == "easy":
            return s["question"]
    return None


async def run_virtual_clarify_experiment(synonym_cases: list[dict], eval_date: str,
                                          conf_threshold: float = 0.7,
                                          memory_on: bool = False) -> dict[str, Any]:
    """虚拟澄清实验（task 3，P2-1/P2-3）：
    阶段 1（无记忆基线）：澄清判定 + golden 模拟用户选择 → 潜在澄清率（拆「歧义且错」/「歧义但对」）
          + 虚拟澄清收益（澄清后 L1 差，主指标）。
    阶段 2（--memory on）：沉淀 source cases + band 分层 → 澄清率随记忆下降
          （只统计 hit/inject 可达项；miss 带歧义项单独报「记忆不可达」）。
    报告标注：golden 模拟完美用户，数字为上限参考；不做真 HITL。"""
    from langgraph.checkpoint.memory import InMemorySaver

    from app.eval.comparator import compare_spec
    from app.graph.graph_builder import init_memory, run_chatbi_graph
    from app.memory.aliases import get_aliases

    catalog = json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text())
    graph_builder.init_graph(InMemorySaver())
    settings.memory_enabled = False

    source_by_id: dict[str, dict] = {}
    if memory_on:
        _d, golden = load_cases(DEFAULT_CASES)
        source_by_id = {c["id"]: c for c in golden if c.get("golden_spec")}

    def _run(q: str, rid: str) -> dict[str, Any]:
        return run_chatbi_graph({
            "run_id": rid, "user_id": "eval", "question": q,
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})

    results: list[dict[str, Any]] = []
    for s in synonym_cases:
        state = await _run(s["question"], f"clar_{s['id']}")
        score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
        intent = state.get("resolved_intent") or {}
        a_l1 = bool(score and score.core_ok)
        amb, reason = _clarify_decision(s["question"], intent, catalog, get_aliases(), conf_threshold)
        clarified = dict(intent)
        clarified["metrics"] = list((s.get("golden_spec") or {}).get("metrics") or [])
        c_score = compare_spec(clarified, s.get("golden_spec"), eval_date)
        results.append({
            "id": s["id"], "question": s["question"], "difficulty": s.get("difficulty", "easy"),
            "a_l1": a_l1, "ambiguous": amb, "clarify_reason": reason,
            "clarified_l1": bool(c_score and c_score.core_ok),
            "conf": float(intent.get("confidence") or 0.0),
            "ambiguous_baseline": amb and not a_l1,  # 歧义且错 = 真需要澄清
        })

    if memory_on:
        settings.memory_enabled = True
        await init_memory(_experiment_memory_path())
        for s in synonym_cases:
            src = source_by_id.get(s.get("source_case"))
            if src is None:
                continue
            await _run(src["question"], f"seed_{src['id']}")
        bands = await _compute_synonym_bands([s["question"] for s in synonym_cases],
                                             settings.memory_namespace)
        for r in results:
            r["band"] = bands[r["question"]]
        for s in synonym_cases:
            state = await _run(s["question"], f"clarM_{s['id']}")
            score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
            intent = state.get("resolved_intent") or {}
            amb_mem, _ = _clarify_decision(s["question"], intent, catalog, get_aliases(), conf_threshold)
            r = next(x for x in results if x["id"] == s["id"])
            r["ambiguous_memory"] = amb_mem and not bool(score and score.core_ok)
        await _close_memory()
    else:
        for r in results:
            r["band"] = "miss"
            r["ambiguous_memory"] = r["ambiguous_baseline"]

    metrics = _virtual_clarify_metrics(results, conf_threshold)
    metrics["band_report"] = _clarify_band_report(results)
    metrics["memory_on"] = memory_on
    metrics["upper_bound_note"] = "golden 模拟完美用户，数字为上限参考；不做真 HITL"
    metrics["per_item"] = results
    return metrics


def _clarify_decision(question: str, intent: dict[str, Any] | None,
                     catalog: list[dict[str, Any]], aliases: dict[str, str] | None,
                     conf_threshold: float) -> tuple[bool, str]:
    """歧义判定（task 3.1）：低置信 OR 多指标候选（别名/catalog 命中 ≥2 个 ID）。"""
    from app.memory.retriever import extract_metric_names

    conf = float((intent or {}).get("confidence") or 0.0)
    if conf < conf_threshold:
        return True, f"low_confidence({conf:.2f}<{conf_threshold})"
    found = extract_metric_names(question, catalog, aliases)
    if len(set(found)) >= 2:
        return True, f"multi_metric_candidates({sorted(set(found))})"
    return False, ""


def _virtual_clarify_metrics(results: list[dict[str, Any]],
                             conf_threshold: float) -> dict[str, Any]:
    """聚合（task 3.2）：潜在澄清率（拆歧义且错/歧义但对）+ 虚拟澄清收益（主指标，澄清后 L1 差）。"""
    n = len(results)
    if not n:
        return {"n": 0, "potential_clarify_rate": "0/0", "ambiguous_error": "0/0",
                "ambiguous_correct": "0/0", "baseline_l1": 0.0, "clarified_l1": 0.0,
                "virtual_gain": 0.0}
    baseline_ok = sum(1 for r in results if r["a_l1"])
    clarified_ok = sum(1 for r in results if r["clarified_l1"])
    amb = [r for r in results if r["ambiguous"]]
    amb_err = sum(1 for r in amb if not r["a_l1"])
    amb_ok = sum(1 for r in amb if r["a_l1"])
    return {
        "n": n,
        "potential_clarify_rate": f"{len(amb)}/{n}",
        "ambiguous_error": f"{amb_err}/{n}",
        "ambiguous_correct": f"{amb_ok}/{n}",
        "baseline_l1": baseline_ok / n,
        "clarified_l1": clarified_ok / n,
        "virtual_gain": (clarified_ok - baseline_ok) / n,
    }


def _clarify_band_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    """澄清率随记忆下降的 band 分层报告（task 3.2，P2-1）：只统计 hit/inject 可达项，miss 单独报记忆不可达。"""
    bands: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        bands.setdefault(r.get("band", "miss"), []).append(r)
    out: dict[str, Any] = {}
    for b in ("hit", "inject", "miss"):
        rs = bands.get(b) or []
        if not rs:
            continue
        base_err = sum(1 for r in rs if r.get("ambiguous_baseline"))
        mem_err = sum(1 for r in rs if r.get("ambiguous_memory"))
        out[b] = {"n": len(rs), "baseline_ambiguous": f"{base_err}/{len(rs)}",
                  "memory_ambiguous": f"{mem_err}/{len(rs)}"}
    return out


def _intents_equal(a: dict[str, Any] | None, b: dict[str, Any] | None) -> bool:
    """同问同答一致率（real_consistency）逐字段口径：复用 eval-metrics 重复对协议定义。
    intent/metrics/dimensions/time_range/filters/ordering 逐字段一致。"""
    if not a or not b:
        return False
    for key in ("intent", "metrics", "dimensions", "ordering"):
        if a.get(key) != b.get(key):
            return False
    ta, tb = (a.get("time_range") or {}), (b.get("time_range") or {})
    for key in ("type", "relative", "absolute", "granularity"):
        if ta.get(key) != tb.get(key):
            return False
    return (a.get("filters") or []) == (b.get("filters") or [])


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
    from app.memory.aliases import get_aliases
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
            if band == "hit" and catalog and not hit_allowed(q, hits[0].entry, catalog, get_aliases()):
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
        results.append({"id": s["id"], "question": s["question"],
                        "difficulty": s.get("difficulty", "easy"),
                        "golden": s.get("golden_spec"), "a_l1": a_ok,
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
    # 按难度分层（easy/hard）
    by_diff: dict[str, dict] = {}
    for r in results:
        d = by_diff.setdefault(r.get("difficulty", "easy"),
                               {"n": 0, "a_ok": 0, "b_ok": 0, "inject_n": 0, "inject_a_ok": 0, "inject_b_ok": 0})
        d["n"] += 1
        d["a_ok"] += int(bool(r["a_l1"]))
        d["b_ok"] += int(bool(r.get("b_l1")))
        if r["band"] == "inject":
            d["inject_n"] += 1
            d["inject_a_ok"] += int(bool(r["a_l1"]))
            d["inject_b_ok"] += int(bool(r.get("b_l1")))
    for d in by_diff.values():
        d["a_l1"] = d["a_ok"] / d["n"] if d["n"] else 0
        d["b_l1"] = d["b_ok"] / d["n"] if d["n"] else 0
        d["inject_a_l1"] = d["inject_a_ok"] / d["inject_n"] if d["inject_n"] else 0
        d["inject_b_l1"] = d["inject_b_ok"] / d["inject_n"] if d["inject_n"] else 0
        d["inject_gain"] = d["inject_b_l1"] - d["inject_a_l1"]
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
        "by_difficulty": by_diff,
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


def _real_session_metrics(per_session: list[dict[str, Any]], platform: str,
                            namespace: str) -> dict[str, Any]:
    """real-session 指标聚合（task 2.1）：x/y 原始计数 + N 量级方向性标注（P2-3）。"""
    n = len(per_session)
    hit_total = sum(1 for x in per_session if x["second_hit"])
    cons_total = sum(1 for x in per_session if x["consistent"])
    persist_total = sum(1 for x in per_session if x["persist_ok"])
    variant_total = sum(1 for x in per_session if x.get("variant"))
    tok_delta = sum(x.get("second_tokens", 0) for x in per_session) - sum(x.get("first_tokens", 0) for x in per_session)
    return {
        "protocol": "real-session",
        "namespace": namespace,
        "session_total": n,
        "hit_total": hit_total,
        "real_hit_rate": f"{hit_total}/{n}",
        "real_hit_rate_pct": _percent(hit_total, n),
        "consistency_total": cons_total,
        "real_consistency": f"{cons_total}/{n}",
        "real_consistency_pct": _percent(cons_total, n),
        "persist_total": persist_total if platform == "mock" else None,
        "real_persist_hits": (f"{persist_total}/{n}" if platform == "mock"
                              else "N/A (real: 强验证=重启服务器，留联调)"),
        "variant_total": variant_total,
        "token_delta_second_minus_first": tok_delta,
        "direction_note": "N=8 量级，方向性基线（单次 miss 即 6-12pp）",
        "persist_note": ("弱验证=close/reopen 文件持久化" if platform == "mock"
                         else "real 平台弱验证 N/A；强验证=两遍 /analyze + 重启服务器"),
    }


async def run_real_session_experiment(cases: list[dict[str, Any]], platform: str,
                                      eval_date: str, session_count: int = 8) -> dict[str, Any]:
    """真实路径记忆评测（real-session 协议，设计 D1/D2/D3）：
    每会话 = 首问（未命中，沉淀）→ [mock 弱验证：close/reopen 同一路径] → 二问（期望命中）
           → 近似问（变体，仅观测，band 任意分层）。
    产出 real_hit_rate / real_consistency / real_persist_hits，带 x/y 原始计数 + N 量级方向性标注。
    - mock 平台：runner 本地 store（临时路径），弱验证自动化（文件持久化）。
    - real 平台：走服务器 /analyze（memoryNamespace 透传），二问命中验证；强验证（重启服务器）留联调。"""
    from app.eval.comparator import compare_spec
    from app.graph.graph_builder import init_memory

    settings.memory_enabled = True  # real-session 协议隐含 --memory on（测的就是记忆）
    _d, syn_cases = load_cases(Path(__file__).with_name("synonym_cases.yaml"))
    sessions = _pick_real_sessions(cases, session_count)
    llm = settings.eval_llm_mode

    memory_path: str | None = None
    if platform == "mock":
        from langgraph.checkpoint.memory import InMemorySaver

        graph_builder.init_graph(InMemorySaver())  # mock 平台需先 init graph（run_chatbi_graph 前置）
        memory_path = _real_session_memory_path()
        await init_memory(memory_path)  # real-session 专用 store，不碰真实 memory.sqlite/memory.lance

    per_session: list[dict[str, Any]] = []
    for s in sessions:
        sid = s["id"]
        # 首问：未命中 → 全链路成功后写钩子沉淀
        before1 = meter.snapshot()
        r1 = await run_case(s, llm, platform, eval_date)
        after1 = meter.snapshot()
        # mock 弱验证：close → reopen 同一路径（文件持久化 claim）
        if platform == "mock":
            from app.graph import nodes as _n
            _first_rows = 0
            if _n.memory is not None:
                try:
                    _first_rows = len(await _n.memory.all(namespace=settings.memory_namespace))
                except Exception:  # noqa: BLE001
                    _first_rows = -1
            await _close_memory()
            await init_memory(memory_path)
        # 二问：期望命中（mock 下已跨 reopen）
        before2 = meter.snapshot()
        r2 = await run_case(s, llm, platform, eval_date)
        after2 = meter.snapshot()
        # 近似问：变体仅观测（band 任意分层，不预设）
        variant = _variant_for(s, syn_cases)
        r3: dict[str, Any] | None = None
        if variant:
            vcase = dict(s)
            vcase["id"] = f"{sid}_variant"
            vcase["question"] = variant
            before3 = meter.snapshot()
            r3 = await run_case(vcase, llm, platform, eval_date)
            after3 = meter.snapshot()
        hit2 = bool(r2.get("memory_hit"))
        score1 = compare_spec(r1.get("resolved_intent"), s.get("golden_spec"), eval_date)
        score2 = compare_spec(r2.get("resolved_intent"), s.get("golden_spec"), eval_date)
        per_session.append({
            "id": sid,
            "question": s["question"],
            "intent_type": (s.get("golden_spec") or {}).get("intent"),
            "first_sql_source": r1.get("sql_source"),
            "first_store_rows": _first_rows if platform == "mock" else None,
            "first_hit": bool(r1.get("memory_hit")),
            "first_l1": bool(score1 and score1.core_ok),
            "second_hit": hit2,
            "second_l1": bool(score2 and score2.core_ok),
            "consistent": _intents_equal(r1.get("resolved_intent"), r2.get("resolved_intent")),
            "persist_ok": hit2,  # mock 下二问已跨 close/reopen；real 下仅跨请求（强验证留联调）
            "variant": variant,
            "variant_band": r3.get("memory_band") if r3 else None,
            "variant_hit": bool(r3.get("memory_hit")) if r3 else None,
            "first_tokens": after1["total_tokens"] - before1["total_tokens"],
            "second_tokens": after2["total_tokens"] - before2["total_tokens"],
        })
        if r3 is not None:
            per_session[-1]["variant_tokens"] = after3["total_tokens"] - before3["total_tokens"]

    if platform == "mock":
        await _close_memory()

    metrics = _real_session_metrics(per_session, platform, settings.memory_namespace)
    metrics["per_session"] = per_session
    return metrics


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
        "sql": (state.get("sql_attempts") or [{}])[-1].get("sql"),
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
        "sql": final_report.get("sql", ""),
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


async def _check_case_result(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any] | None:
    """R1：对 L1 通过的用例，用真实 MySQL 独立执行其合成 SQL 并断言结果（P1 独立审计）。"""
    from app.eval.result_comparator import check_result

    exp = case.get("expected_result")
    if not exp:
        return None  # 无 expected_result → 不可判定（R1=N/A）
    sql = result.get("sql")
    if not sql:
        return {"kind": str(exp.get("type") or ""), "passed": False,
                "detail": "no sql", "fail_reason": "sql_error"}
    rows, err = _exec_mysql(sql)
    if err:
        return {"kind": str(exp.get("type") or ""), "passed": False,
                "detail": f"exec_error: {err}", "fail_reason": "exec_error"}
    check = check_result(rows, exp, intent=str((case.get("golden_spec") or {}).get("intent") or ""))
    if check is None:
        return None
    return {"kind": check.kind, "passed": check.passed, "detail": check.detail,
            "fail_reason": None if check.passed else "value_mismatch"}


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
        "result_judged": sum(1 for r in evaluated if r.get("result_check") is not None),
        "result_passed": sum(1 for r in evaluated if r.get("result_check") is not None and r["result_check"]["passed"]),
        "result_rate": _percent(
            sum(1 for r in evaluated if r.get("result_check") is not None and r["result_check"]["passed"]),
            sum(1 for r in evaluated if r.get("result_check") is not None)),
        "result_value_mismatch": [r["id"] for r in evaluated
                                  if r.get("result_check") and r["result_check"].get("fail_reason") == "value_mismatch"],
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


def _exec_mysql(sql: str, db: str = "video_data_analysis") -> tuple[list[dict[str, Any]], str | None]:
    """评测侧审计执行：用本地 MySQL 独立执行合成 SQL（R1 验证，P1 独立于系统）。

    注意：这是评测 runner 的独立审计路径（非业务主链路；业务执行仍走 Spring SQL Gateway）。
    mysql -B 批处理输出含列名（首行），解析为 list[dict]。
    返回 (rows, err)；err 非空表示执行失败（exec_error）。
    """
    import shutil
    import subprocess

    exe = shutil.which("mysql")
    if exe is None:
        return [], "mysql CLI not found"
    cmd = [exe, "-h", "127.0.0.1", "-u", "root", "-p123456", db, "-B", "-e", sql]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    except subprocess.TimeoutExpired:
        return [], "exec timeout"
    if r.returncode != 0:
        return [], r.stderr.strip()[:200]
    lines = [ln for ln in r.stdout.strip().split("\n") if ln]
    if not lines:
        return [], None
    cols = [c.strip() for c in lines[0].split("\t")]
    rows = []
    for ln in lines[1:]:
        vals = ln.split("\t")
        rows.append({cols[i]: vals[i] if i < len(vals) else None for i in range(len(cols))})
    return rows, None


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
        f"| 结果正确率（R1，可断言口径） | {agg['result_rate']:.2%} | {agg['result_passed']}/{agg['result_judged']}（真实 MySQL 独立执行，seed 42 真值） |",
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
    mismatches = agg.get("result_value_mismatch") or []
    if mismatches:
        lines.extend(["", "## 交叉诊断：L1 对 + R1 错（value_mismatch）", "",
                      "以下用例语义解析正确（L1 通过）但真实执行结果与 seed 42 真值不符——**解析对但 SQL 错的合成器/生成 bug 信号**：",
                      "", "| Case | 失败详情 |", "|---|---|"])
        for result in results:
            rc = result.get("result_check")
            if result["id"] in mismatches and rc:
                lines.append(f"| {result['id']} | {rc.get('detail', '')} |")
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
    parser.add_argument("--protocol", choices=["eval", "real-session"], default="eval",
                        help="评测协议：eval（默认，场内自命中口径）| real-session（真实路径命中率基线）")
    parser.add_argument("--namespace", default=None,
                        help="记忆 namespace 覆盖；仅支持显式 default（真实联调开关），评测 namespace 由协议自动生成")
    parser.add_argument("--real-session-cases", type=int, default=8,
                        help="real-session 会话数（默认 8）")
    parser.add_argument("--virtual-clarify", action="store_true", default=False,
                        help="虚拟澄清实验（需 --synonym-cases；--memory on 加阶段 2 澄清率随记忆下降）")
    args = parser.parse_args()

    if args.compare:
        a = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        b = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        print(compare_reports(a, b))
        return

    run_config = apply_run_config(args.llm, args.platform, args.cassette, args.memory)
    eval_date, cases = load_cases(args.cases)
    run_config["eval_date"] = eval_date

    if args.virtual_clarify:
        if not args.synonym_cases:
            raise SystemExit("--virtual-clarify 需 --synonym-cases 指定同义集")
        _date, syn_cases = load_cases(args.synonym_cases)
        exp = await run_virtual_clarify_experiment(syn_cases, eval_date,
                                                   memory_on=run_config["memory"] == "on")
        print(f"[virtual-clarify] 潜在澄清率={exp['potential_clarify_rate']} "
              f"(歧义且错={exp['ambiguous_error']} / 歧义但对={exp['ambiguous_correct']})")
        print(f"[virtual-clarify] 基线 L1={exp['baseline_l1']:.2%} → 澄清后 L1={exp['clarified_l1']:.2%} "
              f"虚拟收益={exp['virtual_gain']:+.2%}")
        print(f"[virtual-clarify] band_report={exp['band_report']} | {exp['upper_bound_note']}")
        print(json.dumps(exp, ensure_ascii=False, indent=2))
        return

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
            for _d, _m in sorted(exp.get("by_difficulty", {}).items()):
                print(f"[synonym] 难度[{_d}] N={_m['n']} 组A L1={_m['a_l1']:.2%} "
                      f"| inject 子集 B L1={_m['inject_b_l1']:.2%} 增益={_m['inject_gain']:+.2%} "
                      f"(inject_n={_m['inject_n']})")
            if exp["sample_warning"]:
                print("[synonym] WARNING: inject 子集样本不足(<8)，结论仅方向性")
        import json as _json
        print(_json.dumps(exp, ensure_ascii=False, indent=2))
        return

    if args.protocol == "real-session":
        _assert_real_session_valid(run_config["llm"])
        if args.namespace:
            if args.namespace != "default":
                raise SystemExit("--namespace 仅支持显式 default（真实联调开关）；评测 namespace 由协议自动生成")
            settings.memory_namespace = "default"
        else:
            settings.memory_namespace = _real_session_namespace(eval_date)
        exp = await run_real_session_experiment(cases, run_config["platform"], eval_date,
                                                session_count=max(1, args.real_session_cases))
        print(f"[real-session] namespace={settings.memory_namespace} sessions={exp['session_total']}")
        print(f"[real-session] real_hit_rate={exp['real_hit_rate']} "
              f"real_consistency={exp['real_consistency']}")
        print(f"[real-session] real_persist_hits={exp['real_persist_hits']} "
              f"variant_total={exp['variant_total']}")
        print(f"[real-session] {exp['direction_note']}")
        print(json.dumps(exp, ensure_ascii=False, indent=2))
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
