from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

from app.eval.metrics import contains_all, required_fields_present, summarize_results
from app.graph import graph_builder
from app.graph.graph_builder import run_chatbi_graph
from app.settings import settings


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CASES = Path(__file__).with_name("cases.yaml")
DEFAULT_REPORT = ROOT / "docs" / "eval-report.md"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


async def run_case(case: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "real":
        return await run_real_case(case)
    return await run_mock_case(case)


async def run_mock_case(case: dict[str, Any]) -> dict[str, Any]:
    start = time.perf_counter()
    original_validate_sql = graph_builder.platform.validate_sql
    original_execute_sql = graph_builder.platform.execute_sql
    original_check_dq = graph_builder.platform.check_sql_result_dq

    if int(case.get("mock_guard_failures", 0)) > 0:
        graph_builder.platform.validate_sql = _mock_guard(case)
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
    }


async def run_real_case(case: dict[str, Any]) -> dict[str, Any]:
    if httpx is None:
        raise RuntimeError("httpx is required for --mode real")
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(
            f"{settings.platform_base_url.rstrip('/')}/api/agent/analyze",
            params={
                "userId": "eval",
                "message": case["question"],
                "nocache": "true",
                "engine": "langgraph",
            },
        )
        response.raise_for_status()
        payload = response.json()

    final_report = payload.get("finalReport") or payload.get("final_report") or {}
    state = {
        "route": "complex",
        "approval_status": "waiting" if payload.get("status") == "WAITING_APPROVAL" else None,
        "sql_attempts": [{"sql": final_report.get("sql", "")}],
        "sql_retry_count": payload.get("sqlRetryCount", 0),
        "final_report": final_report,
    }
    latency_ms = int((time.perf_counter() - start) * 1000)
    passed, reason = evaluate_case(case, state)
    return {
        "id": case["id"],
        "type": case["type"],
        "passed": passed,
        "reason": reason,
        "latency_ms": latency_ms,
    }


def evaluate_case(case: dict[str, Any], state: dict[str, Any]) -> tuple[bool, str]:
    if expected := case.get("expected_route"):
        if state.get("route") != expected:
            return False, f"route={state.get('route')} expected={expected}"

    if expected_status := case.get("expected_status"):
        status = "WAITING_APPROVAL" if state.get("approval_status") == "waiting" else "SUCCESS"
        if status != expected_status:
            return False, f"status={status} expected={expected_status}"

    if expected_sql := case.get("expected_sql_contains"):
        attempts = state.get("sql_attempts") or []
        sql_text = " ".join(str(attempt.get("sql", "")) for attempt in attempts)
        if not contains_all(sql_text, expected_sql):
            return False, "generated SQL missing expected fragments"

    if expected_fields := case.get("expected_report_fields"):
        if not required_fields_present(state.get("final_report") or {}, expected_fields):
            return False, "final report missing required fields"

    if expected_keywords := case.get("expected_report_keywords"):
        report_text = json.dumps(state.get("final_report") or {}, ensure_ascii=False)
        if not contains_all(report_text, expected_keywords):
            return False, "final report missing expected keywords"

    if "expected_sql_retry_count" in case:
        expected_retry_count = int(case["expected_sql_retry_count"])
        if int(state.get("sql_retry_count", 0)) != expected_retry_count:
            return False, f"sql_retry_count={state.get('sql_retry_count')} expected={expected_retry_count}"

    return True, "PASS"


def _mock_guard(case: dict[str, Any]):
    remaining = {"count": int(case.get("mock_guard_failures", 0))}

    async def validate_sql(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if remaining["count"] > 0:
            remaining["count"] -= 1
            return {
                "pass": False,
                "sql": kwargs["sql"],
                "riskLevel": "MEDIUM",
                "errorCode": "SQL_RULE_WARNING",
                "reason": "eval guard failure",
                "suggestion": "regenerate SQL",
                "accessedTables": ["metric_daily"],
                "violations": [{"code": "SQL_RULE_WARNING", "message": "eval guard failure"}],
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


def _mock_dq(case: dict[str, Any]):
    remaining = {"count": int(case.get("mock_dq_failures", 0))}

    async def check_sql_result_dq(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if remaining["count"] > 0:
            remaining["count"] -= 1
            return {
                "pass": False,
                "riskLevel": "HIGH",
                "reason": "eval dq failure",
                "suggestion": "regenerate SQL",
                "warnings": [],
            }
        warnings = ["partial data"] if case.get("mock_dq_warning") else []
        return {
            "pass": True,
            "riskLevel": "MEDIUM" if warnings else "LOW",
            "reason": None,
            "suggestion": None,
            "warnings": warnings,
        }

    return check_sql_result_dq


def render_report(case_results: list[dict[str, Any]]) -> str:
    metrics = summarize_results(case_results)
    lines = [
        "# DataAgent Evaluation Report",
        "",
        "This report is generated by `python -m app.eval.runner`.",
        "",
        "## Metrics",
        "",
        "| Metric | Passed | Total | Score |",
        "|---|---:|---:|---:|",
    ]
    for metric in metrics:
        lines.append(f"| {metric.name} | {metric.passed} | {metric.total} | {metric.score:.2%} |")

    lines.extend(["", "## Cases", "", "| Case | Type | Result | Latency | Reason |", "|---|---|---|---:|---|"])
    for result in case_results:
        outcome = "PASS" if result["passed"] else "FAIL"
        lines.append(
            f"| {result['id']} | {result['type']} | {outcome} | {result['latency_ms']}ms | {result['reason']} |"
        )
    lines.append("")
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run DataAgent evaluation cases.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--mode", choices=["mock", "real"], default="mock")
    args = parser.parse_args()

    settings.trace_callback_enabled = args.mode == "real"
    settings.platform_calls_enabled = args.mode == "real"

    cases = load_cases(args.cases)
    results = [await run_case(case, args.mode) for case in cases]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(results), encoding="utf-8")
    print(f"wrote {args.report}")


if __name__ == "__main__":
    asyncio.run(main())
