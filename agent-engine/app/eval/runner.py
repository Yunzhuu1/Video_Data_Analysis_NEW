from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

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


def apply_run_config(llm: str | None, platform: str | None, cassette: str | None) -> dict[str, str]:
    """把 --llm / --platform 落到 settings 并校验非法组合，返回自描述运行配置。"""
    if llm is not None:
        settings.eval_llm_mode = llm
    if platform is not None:
        settings.platform_calls_enabled = platform == "real"
    platform_real = settings.platform_calls_enabled

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
    for case in cases:
        try:
            results.append(await run_case(case, llm, platform, eval_date))
        except Exception as exc:  # noqa: BLE001 - environment failure isolation
            results.append(error_result(case, exc))
    return results


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
    }


async def run_graph_case(case: dict[str, Any], eval_date: str) -> dict[str, Any]:
    """mock/replay：跑真实图（LLM 由 settings.eval_llm_mode 控制），平台走 mock。"""
    start = time.perf_counter()
    original_validate_sql = graph_builder.platform.validate_sql
    original_execute_sql = graph_builder.platform.execute_sql
    original_check_dq = graph_builder.platform.check_sql_result_dq

    if int(case.get("mock_guard_failures", 0)) > 0:
        graph_builder.platform.validate_sql = _mock_guard(case)
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
    params = {"userId": "eval", "message": question, "nocache": "true", "includeDebug": "true"}
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


async def run_real_case(case: dict[str, Any], eval_date: str) -> dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx is required for platform=real")
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        response = await _get_analyze(client, case["question"])
    payload = response.json()
    debug = payload.get("debug") or {}
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

    return validate_sql


async def _mock_high_risk(*args, **kwargs):
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
    parser.add_argument("--compare", nargs=2, metavar=("A_JSON", "B_JSON"))
    args = parser.parse_args()

    if args.compare:
        a = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        b = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        print(compare_reports(a, b))
        return

    run_config = apply_run_config(args.llm, args.platform, args.cassette)
    eval_date, cases = load_cases(args.cases)
    run_config["eval_date"] = eval_date

    from app.graph.checkpoints import create_checkpointer

    db_path = ":memory:" if run_config["platform"] == "mock" else settings.checkpoint_db_path
    checkpointer = await create_checkpointer(db_path)
    graph_builder.init_graph(checkpointer)

    results = await run_cases(cases, run_config["llm"], run_config["platform"], eval_date)
    await checkpointer.conn.close()

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
