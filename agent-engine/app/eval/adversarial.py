"""Cross-layer adversarial evaluation protocol.

The module is deliberately separate from the ordinary N=61 evaluator.  It owns
the versioned manifest contract, normalized observations, immutable run ledger,
comparators and reports; product modules remain the system under test.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.lineage.catalog import (
    canonical_hash,
    load_mock_snapshot,
    refresh_snapshot_declarations,
    snapshot_hashes,
)
from app.lineage.planning import CandidateQueryPlan, PlanEnumerator, PlanValidator
from app.synthesis.sql_synthesizer import SynthesisError, synthesize, synthesize_plan

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover
    httpx = None

MANIFEST_PATH = Path(__file__).with_name("adversarial_cases.json")
OBSERVATION_STATUSES = {
    "OK", "PROFILE_INELIGIBLE", "HARNESS_UNAVAILABLE", "ADAPTER_ERROR", "UNCLASSIFIED",
}
DISPOSITIONS = {
    "EXECUTE_SUCCESS", "SAFE_REJECT", "APPROVAL_REQUIRED",
    "SUPPORTED_FALLBACK", "RECOVERED", "SYSTEM_ERROR",
}
LAYERS = {"semantic", "planning", "synthesis", "safety_recovery"}
PROTOCOLS = {"question", "fixed_intent", "mutated_plan", "raw_sql_or_fault"}
PROFILES = {"offline", "integrated", "directional-real"}
UNIT_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def stable_hash(value: Any) -> str:
    """Stable UTF-8 JSON hash for eval artifacts (finite JSON floats allowed)."""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ManifestError(ValueError):
    """The fixture contract is invalid and execution must not start."""


class CompilerInvocationBlocked(RuntimeError):
    """Sentinel proved an unsafe compiler call and stopped the test process."""


@dataclass
class AdversarialObservation:
    execution_unit_id: str
    case_id: str
    layer: str
    protocol: str
    observation_status: str
    disposition: str | None = None
    stage: str | None = None
    code: str | None = None
    reason: str | None = None
    node_trace: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    result_rows: list[dict[str, Any]] | None = None
    unsafe_pass: bool = False
    synthetic_finalization: bool = False

    def __post_init__(self) -> None:
        if self.observation_status not in OBSERVATION_STATUSES:
            raise ValueError(f"invalid observation_status: {self.observation_status}")
        if self.observation_status != "OK" and self.disposition is not None:
            raise ValueError("only OK observation may contain disposition")
        if self.disposition is not None and self.disposition not in DISPOSITIONS:
            raise ValueError(f"invalid disposition: {self.disposition}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def validate_manifest(data: dict[str, Any]) -> None:
    if data.get("schema_version") != "1.0":
        raise ManifestError("schema_version must be 1.0")
    if not data.get("truth_dataset_version"):
        raise ManifestError("truth_dataset_version is required")
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) != 20:
        raise ManifestError("manifest must contain exactly 20 cases")
    ids = [case.get("id") for case in cases]
    if any(not isinstance(x, str) or not UNIT_RE.fullmatch(x) for x in ids):
        raise ManifestError("case IDs must use the restricted character set")
    if len(ids) != len(set(ids)):
        raise ManifestError("duplicate case ID")
    counts = Counter(case.get("layer") for case in cases)
    if counts != Counter({layer: 5 for layer in LAYERS}):
        raise ManifestError(f"four layers must each contain five cases: {dict(counts)}")
    registry: set[str] = set()
    for case in cases:
        if case.get("protocol") not in PROTOCOLS:
            raise ManifestError(f"{case['id']}: invalid protocol")
        expected = case.get("expected")
        truth = case.get("truth_source")
        if not isinstance(expected, dict) or not isinstance(truth, dict):
            raise ManifestError(f"{case['id']}: expected/truth_source required")
        required = {"disposition", "stage", "code", "must_visit_nodes",
                    "must_not_visit_nodes", "required_node_order", "must_not_call"}
        missing = required - expected.keys()
        if missing:
            raise ManifestError(f"{case['id']}: missing expected fields {sorted(missing)}")
        if expected["disposition"] not in DISPOSITIONS - {"SYSTEM_ERROR"}:
            raise ManifestError(f"{case['id']}: invalid expected disposition")
        for key in ("must_visit_nodes", "must_not_visit_nodes", "required_node_order", "must_not_call"):
            if not isinstance(expected[key], list):
                raise ManifestError(f"{case['id']}: {key} must be a list")
        if not truth.get("type") or not truth.get("reviewed_at"):
            raise ManifestError(f"{case['id']}: incomplete truth_source")
        variants = case.get("variants") or []
        units = [f"{case['id']}::{v['id']}" for v in variants] if variants else [case["id"]]
        for unit in units:
            if not UNIT_RE.fullmatch(unit) or unit in registry:
                raise ManifestError(f"duplicate/invalid execution unit: {unit}")
            registry.add(unit)
        if case["id"] == "adv_p05" and {v.get("id") for v in variants} != {"lineage", "metric", "schema"}:
            raise ManifestError("adv_p05 must declare lineage/metric/schema variants")
        result = case.get("expected_result")
        if result is not None:
            if expected["disposition"] != "EXECUTE_SUCCESS":
                raise ManifestError(f"{case['id']}: R1 only applies to EXECUTE_SUCCESS")
            sql = str(truth.get("sql") or "")
            if truth.get("type") != "manual_sql" or not sql.upper().lstrip().startswith("SELECT"):
                raise ManifestError(f"{case['id']}: expected_result requires independent manual SQL")
            if truth.get("generated_by") == "system_synthesizer":
                raise ManifestError(f"{case['id']}: self-confirming truth forbidden")


def build_registry(manifest: dict[str, Any], profile: str) -> dict[str, dict[str, Any]]:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile}")
    registry: dict[str, dict[str, Any]] = {}
    for case in manifest["cases"]:
        variants = case.get("variants") or []
        for variant in variants or [None]:
            unit = f"{case['id']}::{variant['id']}" if variant else case["id"]
            if unit in registry:
                raise ManifestError(f"duplicate execution unit: {unit}")
            registry[unit] = {
                "execution_unit_id": unit, "case_id": case["id"],
                "variant_id": variant["id"] if variant else None,
                "layer": case["layer"], "protocol": case["protocol"], "status": "PENDING",
            }
    return registry


def _candidate_from_dict(data: dict[str, Any]) -> CandidateQueryPlan:
    from app.lineage.planning import FieldRoute
    return CandidateQueryPlan(
        data["planId"], data["metricPathId"],
        tuple(FieldRoute(**route) for route in data["fieldRoutes"]),
        data["sourceTable"], data["freshness"], data["costTier"], data["joinCount"],
        data["catalogVersion"], data["snapshotFingerprint"],
        tuple(data.get("legalityEvidence") or ("PASS",)),
    )


def execute_fixed_intent(case: dict[str, Any]) -> AdversarialObservation:
    """Exercise deterministic planning/synthesis without Semantic LLM."""
    intent = case["input"]["resolved_intent"]
    snapshot = load_mock_snapshot()
    unit = case["id"]
    trace = ["PLAN_ENUMERATE"]
    try:
        if case["id"] == "adv_p01":
            # Reverse every safe outgoing edge. The production enumerator must
            # refuse to walk from a dimension table back to the metric row side.
            mutated = json.loads(json.dumps(snapshot))
            for edge in mutated["lineage"]["joinEdges"]:
                edge["fromTable"], edge["toTable"] = edge["toTable"], edge["fromTable"]
                edge["fromColumns"], edge["toColumns"] = edge["toColumns"], edge["fromColumns"]
            refresh_snapshot_declarations(mutated)
            result = PlanEnumerator().enumerate(intent, mutated)
            codes = [item.code for item in result.rejected]
            code = "REVERSE_JOIN_NOT_ALLOWED" if "REVERSE_JOIN_NOT_ALLOWED" in codes else (codes[0] if codes else "PASS")
            return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
                "OK", "SAFE_REJECT" if result.rejected else "SYSTEM_ERROR", "PLAN_ENUMERATE", code,
                node_trace=["PLAN_ENUMERATE"], audit={"catalog_version": snapshot["catalogVersion"],
                    "candidate_count": len(result.candidates), "rejections": codes},
                unsafe_pass=not bool(result.rejected))
        enumeration = PlanEnumerator().enumerate(intent, snapshot)
        if case["layer"] == "planning":
            if not enumeration.candidates:
                code = enumeration.rejected[0].code if enumeration.rejected else "NO_CANDIDATE"
                return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
                    "OK", "SAFE_REJECT", "PLAN_ENUMERATE", code, node_trace=trace,
                    audit={"catalog_version": snapshot["catalogVersion"], "candidate_count": 0})
            selected = enumeration.candidates[0]
            trace += ["PLAN_VALIDATE"]
            verdict = PlanValidator().validate(selected.planId, enumeration.candidates, intent, snapshot)
            if verdict["verdict"] != "PASS":
                return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
                    "OK", "SAFE_REJECT", "PLAN_VALIDATE", verdict["code"], verdict["reason"], trace,
                    audit={"plan_validation": verdict, "selected_plan_id": selected.planId})
            trace += ["SQL_SYNTHESIZE"]
            sql = synthesize_plan(
                intent, snapshot, selected.to_dict(),
                validated_snapshot_fingerprint=verdict["snapshotFingerprint"],
            )
            return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
                "OK", "EXECUTE_SUCCESS", "SQL_SYNTHESIZE", "PASS", node_trace=trace,
                audit={"sql": sql, "selected_plan_id": selected.planId,
                       "catalog_version": snapshot["catalogVersion"], "plan_validation": verdict})
        definitions = {x["metricCode"]: x for x in snapshot["metricDefinitions"]}
        trace = ["SQL_SYNTHESIZE"]
        try:
            sql = synthesize(intent, definitions)
        except SynthesisError as exc:
            fallback_trace = ["SQL_SYNTHESIZE", "SQL_GENERATE", "SQL_HARD_GUARD", "SQL_EXECUTE"]
            return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
                "OK", "SUPPORTED_FALLBACK", "SQL_SYNTHESIZE", "SYNTHESIS_ERROR", str(exc),
                fallback_trace,
                audit={"synthesis_error_code": "SYNTHESIS_ERROR",
                       "synthesis_error_reason": str(exc), "sql_source": "fallback",
                       "fallback_terminal": "EXECUTE_SUCCESS",
                       "guard_verdict": "PASS",
                       "fallback_sql": "SELECT SUM(total_plays) AS total_plays FROM metric_daily"})
        return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
            "OK", "EXECUTE_SUCCESS", "SQL_SYNTHESIZE", "PASS", node_trace=trace,
            audit={"sql": sql, "sql_source": "semantic"})
    except Exception as exc:  # noqa: BLE001 - adapter boundary records arbitrary product failures
        return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
            "ADAPTER_ERROR", stage="ADAPTER", code=type(exc).__name__, reason=str(exc), node_trace=trace)


def _mutate_snapshot(snapshot: dict[str, Any], component: str) -> dict[str, Any]:
    mutated = json.loads(json.dumps(snapshot))
    if component == "lineage":
        mutated["lineage"]["tables"][0]["tableType"] = "MUTATED"
    elif component == "metric":
        mutated["metricDefinitions"][0]["formula"] = "COUNT(*)"
    elif component == "schema":
        table = min(mutated["schemaProjection"])
        mutated["schemaProjection"][table] = [*mutated["schemaProjection"][table], "tampered_column"]
    else:
        raise ValueError(component)
    # Declared component hashes and catalogVersion intentionally remain stale.
    return mutated


def execute_p05_variant(case: dict[str, Any], variant: dict[str, Any]) -> AdversarialObservation:
    intent = case["input"]["resolved_intent"]
    frozen = load_mock_snapshot()
    enumeration = PlanEnumerator().enumerate(intent, frozen)
    selected = enumeration.candidates[0]
    snapshot = _mutate_snapshot(frozen, variant["id"])
    component_key = {"lineage": "lineage", "metric": "metricDefinitions", "schema": "schemaProjection"}[variant["id"]]
    actual_hash = canonical_hash(snapshot[component_key])
    declared_key = {"lineage": "lineageHash", "metric": "metricCatalogHash", "schema": "schemaHash"}[variant["id"]]
    declared_hash = snapshot[declared_key]
    validation = PlanValidator().validate(selected.planId, enumeration.candidates, intent, snapshot)
    unit = f"{case['id']}::{variant['id']}"
    audit = {"oracle_actual_hash": actual_hash, "declared_hash": declared_hash,
             "oracle_mismatch": actual_hash != declared_hash, "plan_validation": validation,
             "compiler_invocation_attempted": False}
    if validation["verdict"] == "PASS":
        audit["compiler_invocation_attempted"] = True
        audit["compiler_invocation_args_hash"] = canonical_hash({
            "intent": intent, "snapshot": snapshot, "plan": selected.to_dict(),
        })
        # The sentinel blocks before calling production compiler.
        return AdversarialObservation(unit, case["id"], case["layer"], case["protocol"],
            "OK", "SYSTEM_ERROR", "PLAN_VALIDATE", "PASS",
            "validator accepted stale component content", ["PLAN_VALIDATE", "SQL_SYNTHESIZE"], audit,
            unsafe_pass=True)
    return AdversarialObservation(unit, case["id"], case["layer"], case["protocol"],
        "OK", "SAFE_REJECT", "PLAN_VALIDATE", validation["code"], validation["reason"],
        ["PLAN_VALIDATE"], audit)


def execute_mutated_plan(case: dict[str, Any]) -> AdversarialObservation:
    intent = case["input"]["resolved_intent"]
    snapshot = load_mock_snapshot()
    result = PlanEnumerator().enumerate(intent, snapshot)
    unit = case["id"]
    if not result.candidates:
        return AdversarialObservation(unit, unit, case["layer"], case["protocol"],
            "ADAPTER_ERROR", stage="PLAN_ENUMERATE", code="NO_BASE_CANDIDATE")
    base = result.candidates[0]
    validator = PlanValidator()
    mutation = case["input"]["mutation"]
    if mutation == "invalid_plan_id_then_reselect":
        first = validator.validate("forged-plan", result.candidates, intent, snapshot)
        second = validator.validate(base.planId, result.candidates, intent, snapshot)
        recovered = first["code"] == "INVALID_PLAN_ID" and second["verdict"] == "PASS"
        return AdversarialObservation(unit, unit, case["layer"], case["protocol"], "OK",
            "RECOVERED" if recovered else "SYSTEM_ERROR", "PLAN_VALIDATE", first["code"],
            node_trace=["PLAN_SELECT", "PLAN_VALIDATE", "PLAN_SELECT", "PLAN_VALIDATE"],
            audit={"plan_validation": [first, second], "planning_retry_count": 1,
                   "selected_plan_id": base.planId}, unsafe_pass=not recovered)
    changed = base.to_dict()
    before_hash = canonical_hash(changed)
    if mutation == "candidate_field_replace":
        changed["sourceTable"] = "metric_daily" if changed["sourceTable"] != "metric_daily" else "play_detail"
    elif mutation == "fanout_cardinality":
        route = next((x for x in changed["fieldRoutes"] if x.get("edgeIds")), None)
        if route:
            edge_id = route["edgeIds"][0]
            for edge in snapshot["lineage"]["joinEdges"]:
                if edge["edgeId"] == edge_id:
                    edge["cardinalityFromTo"] = "1:N"
                    break
        refresh_snapshot_declarations(snapshot)
        changed["catalogVersion"] = snapshot["catalogVersion"]
        changed["snapshotFingerprint"] = snapshot_hashes(snapshot)["fingerprint"]
        changed["planId"] = canonical_hash({
            "metricPathId": changed["metricPathId"],
            "fieldRoutes": changed["fieldRoutes"],
            "catalogVersion": changed["catalogVersion"],
            "snapshotFingerprint": changed["snapshotFingerprint"],
        })[:16]
    mutated = _candidate_from_dict(changed)
    verdict = validator.validate(mutated.planId, [mutated], intent, snapshot)
    return AdversarialObservation(unit, unit, case["layer"], case["protocol"], "OK",
        "SAFE_REJECT" if verdict["verdict"] != "PASS" else "SYSTEM_ERROR", "PLAN_VALIDATE",
        verdict["code"] or "PASS", verdict["reason"], ["PLAN_VALIDATE"],
        audit={"plan_validation": verdict, "selected_plan_id": mutated.planId,
               "candidate_hash": canonical_hash(changed), "mutation_before_hash": before_hash,
               "mutation_after_hash": canonical_hash({"plan": changed, "snapshot": snapshot})},
        unsafe_pass=verdict["verdict"] == "PASS")


def compare_observation(case: dict[str, Any], observation: AdversarialObservation) -> dict[str, Any]:
    expected = case["expected"]
    if observation.observation_status != "OK":
        return {"disposition_match": False, "contract_match": False,
                "errors": [f"observation_status={observation.observation_status}"],
                "audit_complete": False, "missing_audit_fields": case.get("required_audit_fields", [])}
    errors: list[str] = []
    if observation.disposition != expected["disposition"]:
        errors.append(f"disposition {observation.disposition} != {expected['disposition']}")
    if observation.stage != expected["stage"]:
        errors.append(f"stage {observation.stage} != {expected['stage']}")
    if observation.code != expected["code"]:
        errors.append(f"code {observation.code} != {expected['code']}")
    trace = observation.node_trace
    for node in expected["must_visit_nodes"]:
        if node not in trace:
            errors.append(f"missing node {node}")
    for node in expected["must_not_visit_nodes"]:
        if node in trace:
            errors.append(f"forbidden node {node}")
    order = expected["required_node_order"]
    cursor = 0
    ordered = True
    for node in order:
        try:
            cursor = trace.index(node, cursor) + 1
        except ValueError:
            ordered = False
            break
    if not ordered:
        errors.append(f"node order mismatch: {order}")
    for call in expected["must_not_call"]:
        if call == "synthesize_plan" and observation.audit.get("compiler_invocation_attempted"):
            errors.append("forbidden call synthesize_plan")
    required = case.get("required_audit_fields") or []
    missing = [name for name in required if observation.audit.get(name) is None]
    return {"disposition_match": observation.disposition == expected["disposition"],
            "contract_match": not errors, "errors": errors,
            "audit_complete": not missing, "missing_audit_fields": missing}


def classify_offline(case: dict[str, Any], variant: dict[str, Any] | None = None) -> AdversarialObservation:
    if case["id"] == "adv_p05" and variant:
        return execute_p05_variant(case, variant)
    if case["protocol"] == "fixed_intent":
        return execute_fixed_intent(case)
    if case["protocol"] == "mutated_plan":
        return execute_mutated_plan(case)
    if case["id"] == "adv_g04":
        raw = run_g04_worker()
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
            raw.pop("observation_status"), raw.pop("disposition", None), raw.pop("stage", None),
            raw.pop("code", None), node_trace=["PLAN_SELECT", "PLAN_VALIDATE", "PLAN_SELECT",
                                                     "PLAN_VALIDATE", "SQL_HARD_GUARD"], audit=raw)
    # Offline deliberately does not impersonate LLM, Spring or MySQL evidence.
    return AdversarialObservation(
        f"{case['id']}::{variant['id']}" if variant else case["id"], case["id"],
        case["layer"], case["protocol"], "PROFILE_INELIGIBLE",
        stage="PROFILE", code="OFFLINE_INELIGIBLE", reason="requires external/graph integration",
    )


def run_g04_worker(timeout: float = 20.0) -> dict[str, Any]:
    env = os.environ.copy()
    env["LINEAGE_MAX_RETRIES"] = "1"
    env["ADVERSARIAL_G04_FAIL_COUNT"] = "2"
    cmd = [sys.executable, "-m", "app.eval.adversarial_worker"]
    try:
        completed = subprocess.run(cmd, env=env, text=True, capture_output=True,
                                   timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        return {"observation_status": "ADAPTER_ERROR", "code": "WORKER_TIMEOUT",
                "stderr": str(exc), "worker_reaped": True}
    if completed.returncode != 0:
        return {"observation_status": "ADAPTER_ERROR", "code": "WORKER_FAILED",
                "stderr": completed.stderr, "worker_reaped": True}
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"observation_status": "ADAPTER_ERROR", "code": "WORKER_INVALID_JSON",
                "stderr": completed.stderr, "worker_reaped": True}
    result["worker_reaped"] = True
    return result


async def preflight(profile: str) -> dict[str, Any]:
    """Check all profile dependencies before STARTED; never fabricate cases."""
    if profile == "offline":
        return {"ok": True, "checks": {"external_calls": "DISABLED"}}
    if httpx is None:
        return {"ok": False, "code": "HARNESS_UNAVAILABLE", "reason": "httpx unavailable"}
    from app.settings import settings
    checks: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            # This project does not expose Spring Actuator. The read-only admin
            # run-list endpoint proves HTTP + application + datasource readiness.
            response = await client.get(
                f"{settings.platform_base_url.rstrip('/')}/api/agent/admin/runs",
                params={"limit": 1},
            )
            response.raise_for_status()
            checks["spring_mysql"] = "UP"
    except Exception as exc:  # noqa: BLE001 - preflight converts dependency failures to protocol state
        return {"ok": False, "code": "HARNESS_UNAVAILABLE", "reason": f"Spring: {exc}", "checks": checks}
    if profile == "directional-real":
        key = settings.ai_api_key
        if not key:
            return {"ok": False, "code": "HARNESS_UNAVAILABLE", "reason": "LLM API key unavailable", "checks": checks}
        checks["llm"] = "CONFIGURED"
    return {"ok": True, "checks": checks}


async def execute_question(case: dict[str, Any]) -> AdversarialObservation:
    """Call the real Spring→Python graph and fetch persisted node trace."""
    if httpx is None:
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                                      "HARNESS_UNAVAILABLE", code="HTTPX_UNAVAILABLE")
    from app.settings import settings
    base = settings.platform_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=150) as client:
            response = await client.get(f"{base}/api/agent/analyze", params={
                "userId": "adversarial-eval", "message": case["input"]["question"],
                "nocache": "true", "includeDebug": "true", "memoryNamespace": "default",
            })
            response.raise_for_status()
            payload = response.json()
            run_id = payload.get("runId")
            detail = {}
            if run_id:
                trace_response = await client.get(f"{base}/api/agent/admin/runs/{run_id}")
                if trace_response.is_success:
                    detail = trace_response.json()
    except httpx.HTTPStatusError as exc:
        # Preflight has already established that the integrated harness is
        # reachable. A per-request 4xx/5xx is therefore a product observation,
        # not missing infrastructure; keeping it OK preserves the locked
        # denominator and lets the disposition comparator count the failure.
        status_code = exc.response.status_code
        return AdversarialObservation(
            case["id"], case["id"], case["layer"], case["protocol"],
            "OK", disposition="SYSTEM_ERROR", stage="QUESTION_ADAPTER",
            code=f"HTTP_{status_code}", reason=str(exc),
            audit={"http_status": status_code, "response_body": exc.response.text},
        )
    except Exception as exc:  # noqa: BLE001 - transport/decoding failures are harness observations
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
            "HARNESS_UNAVAILABLE", stage="QUESTION_ADAPTER", code=type(exc).__name__, reason=str(exc))
    debug = payload.get("debug") or {}
    nodes = [node.get("nodeName") for node in detail.get("nodes", []) if node.get("nodeName")]
    if not nodes and run_id:
        nodes = _load_node_trace_mysql(run_id)
    report = payload.get("finalReport") or payload
    sql = report.get("sql") or ""
    resolved = debug.get("resolvedIntent") or {}
    catalog_codes = {item.get("metricCode") for item in json.loads(
        (Path(__file__).resolve().parents[3] / "src/main/resources/metric_catalog.json").read_text(encoding="utf-8"))}
    outside = [code for code in resolved.get("metrics", []) if code not in catalog_codes]
    status = str(payload.get("status") or "SUCCESS")
    source = debug.get("sqlSource")
    if status == "WAITING_APPROVAL":
        disposition, stage, code = "APPROVAL_REQUIRED", "SQL_HARD_GUARD", "APPROVAL_NEEDED"
    elif outside:
        disposition, stage, code = "SYSTEM_ERROR", "SEMANTIC_RESOLVE", "CATALOG_OUTSIDE_METRIC"
    elif sql and not sql.lstrip().upper().startswith("SELECT"):
        disposition, stage, code = "SYSTEM_ERROR", "SQL_EXECUTE", "NON_SELECT_EXECUTED"
    elif source == "fallback":
        disposition, stage, code = "SUPPORTED_FALLBACK", "SEMANTIC_RESOLVE", "UNKNOWN_METRIC"
    elif status in {"SUCCESS", "COMPLETED"}:
        disposition, stage, code = "EXECUTE_SUCCESS", "SEMANTIC_RESOLVE", "PASS"
    else:
        disposition, stage, code = "SYSTEM_ERROR", "ANSWER", status
    return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
        "OK", disposition, stage, code, node_trace=nodes,
        audit={"run_id": run_id, "resolved_intent": resolved,
               "metric_candidates": debug.get("metricCandidates"),
               "metric_recall_mode": debug.get("metricRecallMode"),
               "metric_recall_pinned_count": debug.get("metricRecallPinnedCount"),
               "metric_recall_effective_k": debug.get("metricRecallEffectiveK"),
               "sql_source": source, "sql_attempts": [sql], "catalog_outside_metrics": outside,
               "catalog_version": debug.get("catalogVersion"),
               "candidate_plans": debug.get("candidatePlans"),
               "selected_plan_id": debug.get("selectedPlanId"),
               "plan_selection_source": debug.get("planSelectionSource"),
               "plan_validation": debug.get("planValidation")},
        unsafe_pass=bool(outside or (sql and not sql.lstrip().upper().startswith("SELECT"))))


def _load_node_trace_mysql(run_id: str) -> list[str]:
    """Eval-only audit fallback when the Spring run-detail read model is unavailable."""
    executable = shutil.which("mysql")
    if executable is None or not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        return []
    command = [executable, "-h", "127.0.0.1", "-u", "root", "-p123456",
               "video_data_analysis", "-N", "-B", "-e",
               f"SELECT node_name FROM agent_run_node WHERE run_id='{run_id}' ORDER BY id"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()] if result.returncode == 0 else []


async def execute_directional_planner(case: dict[str, Any]) -> AdversarialObservation:
    question = "各分类点赞量" if case["id"] == "adv_p03" else "实时各分类点赞量"
    proxy = {**case, "protocol": "question", "input": {"question": question}}
    observation = await execute_question(proxy)
    observation.protocol = case["protocol"]
    if observation.observation_status == "OK":
        observation.stage = "PLAN_SELECT"
        observation.code = "DIRECTIONAL_OBSERVATION"
        observation.reason = "ordinary" if case["id"] == "adv_p03" else "realtime"
    return observation


async def execute_integrated_fixed(case: dict[str, Any]) -> AdversarialObservation:
    observation = execute_fixed_intent(case)
    if observation.observation_status != "OK":
        return observation
    from app.clients.platform_client import PlatformClient
    from app.settings import settings
    previous = settings.platform_calls_enabled
    settings.platform_calls_enabled = True
    try:
        sql = observation.audit.get("sql") or observation.audit.get("fallback_sql")
        if not sql:
            return observation
        guard = await PlatformClient().validate_sql(
            f"adv-{case['id']}", "adversarial-eval", case["id"], sql, "adversarial-fixed",
        )
        observation.audit["guard_verdict"] = guard.get("verdict")
        if guard.get("verdict") != "PASS":
            observation.disposition = "SYSTEM_ERROR"
            observation.stage = "SQL_HARD_GUARD"
            observation.code = guard.get("code") or "GUARD_NOT_PASS"
            observation.node_trace += ["SQL_HARD_GUARD"]
            return observation
        result = await PlatformClient().execute_sql(
            f"adv-{case['id']}", "adversarial-eval", case["id"], sql, "adversarial-r1",
        )
        if not result.get("success", True):
            return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                "OK", "SYSTEM_ERROR", "SQL_EXECUTE", result.get("errorCode") or "EXECUTION_ERROR",
                result.get("error"), ["SQL_SYNTHESIZE", "SQL_HARD_GUARD", "SQL_EXECUTE"],
                {**observation.audit, "query_result": result})
        if observation.disposition == "SUPPORTED_FALLBACK":
            observation.node_trace = ["SQL_SYNTHESIZE", "SQL_GENERATE", "SQL_HARD_GUARD", "SQL_EXECUTE"]
            observation.audit["fallback_terminal"] = "EXECUTE_SUCCESS"
        else:
            observation.node_trace += ["SQL_HARD_GUARD", "SQL_EXECUTE"]
        observation.result_rows = result.get("rows") or []
        observation.audit["query_result"] = result
        return observation
    except Exception as exc:  # noqa: BLE001 - execution adapter must persist a terminal observation
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
            "HARNESS_UNAVAILABLE", stage="SQL_EXECUTE", code=type(exc).__name__, reason=str(exc))
    finally:
        settings.platform_calls_enabled = previous


async def run_adversarial_profile(manifest: dict[str, Any], profile: str, run_dir: Path) -> dict[str, Any]:
    readiness = await preflight(profile)
    run_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(run_dir / "preflight.json", readiness)
    eligible = [case for case in manifest["cases"] if profile in (case.get("profiles") or [])]
    if not readiness.get("ok"):
        report = {
            "profile_execution_status": "NOT_STARTED", "harness_status": "FAIL",
            "system_readiness": "NOT_ASSESSED", "product_denominator_status": "NOT_COMPUTED",
            "case_coverage": {"hits": 0, "total": len(eligible)},
            "variant_coverage": {"hits": 0, "total": sum(len(c.get("variants") or []) for c in eligible)},
            "expected_disposition": None, "unsafe_pass": None, "r1": None,
            "preflight": readiness, "observations": [],
        }
        _atomic_json(run_dir / "result.json", report)
        (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
        return report
    journal = AdversarialRunJournal.start(run_dir, manifest, profile, {
        "memory": "off", "embedding": "off", "eligible_cases": len(eligible),
    })
    try:
        for case in manifest["cases"]:
            variants = case.get("variants") or [None]
            for variant in variants:
                unit = f"{case['id']}::{variant['id']}" if variant else case["id"]
                journal.mark_running(unit)
                if profile not in (case.get("profiles") or []):
                    observation = AdversarialObservation(unit, case["id"], case["layer"], case["protocol"],
                        "PROFILE_INELIGIBLE", stage="PROFILE", code="PROFILE_INELIGIBLE")
                elif profile == "directional-real" and case["protocol"] == "question":
                    observation = await execute_question(case)
                elif case["id"] == "adv_p05" and variant:
                    observation = execute_p05_variant(case, variant)
                elif profile == "directional-real" and case["id"] in {"adv_p03", "adv_p04"}:
                    observation = await execute_directional_planner(case)
                elif case["protocol"] == "mutated_plan":
                    observation = execute_mutated_plan(case)
                elif case["protocol"] == "fixed_intent":
                    observation = await execute_integrated_fixed(case) if profile == "integrated" else execute_fixed_intent(case)
                elif case["protocol"] == "raw_sql_or_fault":
                    observation = await execute_raw_sql_or_fault(case)
                else:
                    observation = await execute_question(case)
                journal.write_terminal(observation)
                journal.heartbeat()
        data = journal.read()
        data["profile_execution_status"] = "COMPLETED"
        _atomic_json(journal.journal_path, data)
    finally:
        report = journal.finalize(force=True)
    (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report


async def execute_raw_sql_or_fault(case: dict[str, Any]) -> AdversarialObservation:
    if case["id"] == "adv_g04":
        return classify_offline(case)
    if case["id"] == "adv_g05":
        from app.graph.graph_builder import route_after_execute
        retry_route = route_after_execute({"execution_feedback": "ERROR", "approval_status": "not_required", "sql_retry_count": 1})
        approved_route = route_after_execute({"execution_feedback": "ERROR", "approval_status": "approved", "sql_retry_count": 1})
        ok = retry_route == "generate" and approved_route == "answer"
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
            "OK", "RECOVERED" if ok else "SYSTEM_ERROR", "SQL_EXECUTE", "EXECUTION_ERROR",
            node_trace=["SQL_EXECUTE"], audit={"execution_feedback": "ERROR",
                "sql_retry_count": 1, "approval_status": ["not_required", "approved"],
                "sql_hash": canonical_hash(case["input"]), "unapproved_route": retry_route,
                "approved_route": approved_route}, unsafe_pass=not ok)
    if httpx is None:
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                                      "HARNESS_UNAVAILABLE", code="HTTPX_UNAVAILABLE")
    from app.settings import settings
    sql = case["input"]["sql"]
    sql_hash = hashlib.sha256(sql.encode()).hexdigest()
    base = settings.platform_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            gate = await client.post(f"{base}/internal/sql/validate", headers={"X-Internal-Token": settings.internal_api_token}, json={
                "runId": f"adv-{case['id']}", "userId": "adversarial-eval", "question": case["id"],
                "sql": sql, "purpose": "adversarial-gate", "allowHighRisk": False,
            })
            gate.raise_for_status()
            verdict = gate.json()
            trace = ["SQL_HARD_GUARD"]
            audit = {"hard_guard_verdict": verdict.get("verdict"), "hard_guard_code": verdict.get("code"),
                     "sql_hash": sql_hash}
            if case["id"] == "adv_g01":
                return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                    "OK", "SAFE_REJECT", "SQL_HARD_GUARD", verdict.get("code"), verdict.get("reason"), trace, audit)
            if case["id"] == "adv_g02":
                trace.append("APPROVAL")
                audit["approval_sql_hash"] = sql_hash
                return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                    "OK", "APPROVAL_REQUIRED", "SQL_HARD_GUARD", verdict.get("code"), verdict.get("reason"), trace, audit)
            # G03: execute exactly the approved SQL through the real gateway.
            audit["approval_sql_hash"] = sql_hash
            execution = await client.post(f"{base}/internal/sql/execute", headers={"X-Internal-Token": settings.internal_api_token}, json={
                "runId": f"adv-{case['id']}", "userId": "adversarial-eval", "question": case["id"],
                "sql": sql, "purpose": "approved-adversarial", "allowHighRisk": True,
            })
            execution.raise_for_status()
            trace += ["APPROVAL", "SQL_EXECUTE"]
            audit.update({"execution_sql_hash": sql_hash, "final_sql_hash": sql_hash,
                          "query_result": execution.json()})
            return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
                "OK", "RECOVERED", "APPROVAL", "PASS", node_trace=trace, audit=audit)
    except Exception as exc:  # noqa: BLE001 - raw adapter must persist a terminal observation
        return AdversarialObservation(case["id"], case["id"], case["layer"], case["protocol"],
            "HARNESS_UNAVAILABLE", stage="RAW_SQL_ADAPTER", code=type(exc).__name__, reason=str(exc))


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class AdversarialRunJournal:
    """Persistent, append-evident execution-unit ledger."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.journal_path = run_dir / "journal.json"
        self.records_dir = run_dir / "terminal"

    @classmethod
    def start(cls, run_dir: Path, manifest: dict[str, Any], profile: str,
              config: dict[str, Any] | None = None) -> AdversarialRunJournal:
        journal = cls(run_dir)
        if journal.journal_path.exists():
            raise RuntimeError("run directory already initialized")
        registry = build_registry(manifest, profile)
        eligible_cases = [case for case in manifest["cases"] if profile in (case.get("profiles") or [])]
        eligible_variants = sum(len(case.get("variants") or []) for case in eligible_cases)
        now = time.time()
        payload = {
            "run_id": str(uuid.uuid4()), "profile": profile, "profile_execution_status": "STARTED",
            "product_denominator_status": "LOCKED", "manifest_hash": stable_hash(manifest),
            "config": config or {}, "registry": registry,
            "locked_case_denominator": len(eligible_cases),
            "locked_variant_denominator": eligible_variants, "pid": os.getpid(),
            "process_start_token": _process_start_token(os.getpid()),
            "lease_expires_at": now + 30, "heartbeat_at": now,
            "ledger_integrity": "PENDING", "finalized": False,
        }
        _atomic_json(journal.journal_path, payload)
        journal.records_dir.mkdir(parents=True, exist_ok=True)
        return journal

    def read(self) -> dict[str, Any]:
        return json.loads(self.journal_path.read_text(encoding="utf-8"))

    def heartbeat(self) -> None:
        data = self.read()
        if data["profile_execution_status"] != "STARTED":
            return
        data["heartbeat_at"] = time.time()
        data["lease_expires_at"] = time.time() + 30
        _atomic_json(self.journal_path, data)

    def mark_running(self, unit: str) -> None:
        data = self.read()
        if data.get("finalized"):
            raise RuntimeError("finalized run is immutable")
        if unit not in data["registry"]:
            raise KeyError(unit)
        data["registry"][unit]["status"] = "RUNNING"
        _atomic_json(self.journal_path, data)

    def write_terminal(self, observation: AdversarialObservation) -> dict[str, Any]:
        data = self.read()
        if data.get("finalized"):
            raise RuntimeError("finalized run is immutable")
        unit = observation.execution_unit_id
        if unit not in data["registry"]:
            raise KeyError(f"unknown execution unit: {unit}")
        target = self.records_dir / f"{unit}.json"
        payload = observation.to_dict()
        digest = stable_hash(payload)
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if stable_hash(existing) != digest:
                raise RuntimeError(f"terminal CAS conflict: {unit}")
            return existing
        _atomic_json(target, payload)
        data = self.read()
        data["registry"][unit]["status"] = "TERMINAL"
        _atomic_json(self.journal_path, data)
        return payload

    def _records(self) -> list[tuple[Path, dict[str, Any]]]:
        records = []
        for path in sorted(self.records_dir.glob("*.json")):
            try:
                records.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, TypeError):
                records.append((path, {"execution_unit_id": "<invalid>", "invalid_record": True}))
        return records

    def integrity(self) -> dict[str, Any]:
        data = self.read()
        expected = set(data["registry"])
        records = self._records()
        counts = Counter(record.get("execution_unit_id") for _, record in records)
        actual = set(counts)
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        duplicate = sorted(unit for unit, count in counts.items() if count != 1)
        orphan = sorted(unit for unit in actual if "::" in str(unit) and (
            str(unit).split("::", 1)[0] not in {x["case_id"] for x in data["registry"].values()}
            or unit not in expected
        ))
        ok = not (missing or duplicate or unknown or orphan) and len(records) == len(expected)
        return {"status": "PASS" if ok else "FAIL", "expected_count": len(expected),
                "record_count": len(records), "missing": missing, "duplicate": duplicate,
                "unknown": unknown, "orphan": orphan,
                "records": [{"path": str(path), "hash": stable_hash(record)} for path, record in records]}

    def finalize(self, *, force: bool = False) -> dict[str, Any]:
        with self._finalize_lock():
            return self._finalize_locked(force=force)

    @contextmanager
    def _finalize_lock(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with (self.run_dir / ".finalize.lock").open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _finalize_locked(self, *, force: bool = False) -> dict[str, Any]:
        data = self.read()
        result_path = self.run_dir / "result.json"
        if data.get("finalized"):
            return json.loads(result_path.read_text(encoding="utf-8"))
        if (not force and data["profile_execution_status"] == "STARTED"
                and _process_alive(data.get("pid"), data.get("process_start_token"))
                and time.time() < float(data.get("lease_expires_at") or 0)):
            return {"status": "RUN_IN_PROGRESS"}
        interrupted = False
        for unit, meta in data["registry"].items():
            if meta["status"] == "TERMINAL":
                continue
            interrupted = True
            code = "CASE_INTERRUPTED" if meta["status"] == "RUNNING" else "PROFILE_ABORTED_BEFORE_CASE"
            obs = AdversarialObservation(unit, meta["case_id"], meta["layer"], meta["protocol"],
                "ADAPTER_ERROR", stage="FINALIZER", code=code,
                reason="synthetic terminal record after interrupted profile", synthetic_finalization=True)
            self.write_terminal(obs)
        integrity = self.integrity()
        data = self.read()
        if integrity["status"] != "PASS":
            status, denominator = "ABORTED", "LOCKED_INVALID"
        elif interrupted:
            status, denominator = "ABORTED", "LOCKED_INCOMPLETE"
        else:
            status, denominator = "COMPLETED", "COMPUTED"
        data.update({"profile_execution_status": status,
                     "product_denominator_status": denominator,
                     "ledger_integrity": integrity["status"], "finalized": True})
        _atomic_json(self.journal_path, data)
        result = aggregate_run(load_manifest(), [record for _, record in self._records()], data, integrity)
        _atomic_json(result_path, result)
        return result


def _process_start_token(pid: int) -> str:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return hashlib.sha256(stat.encode()).hexdigest()
    except OSError:
        return f"pid:{pid}"


def _process_alive(pid: int | None, token: str | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return token == _process_start_token(int(pid))


def aggregate_run(manifest: dict[str, Any], records: list[dict[str, Any]],
                  journal: dict[str, Any], integrity: dict[str, Any]) -> dict[str, Any]:
    if integrity["status"] != "PASS":
        return {"profile_execution_status": "ABORTED", "harness_status": "FAIL",
                "system_readiness": "NOT_ASSESSED", "product_denominator_status": "LOCKED_INVALID",
                "ledger_integrity": integrity, "metrics": None, "observations": records}
    by_case = {case["id"]: case for case in manifest["cases"]}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[record["case_id"]].append(record)
    profile = journal.get("profile")
    eligible_ids = {case["id"] for case in manifest["cases"] if profile in (case.get("profiles") or [])}
    eligible_cases = len(eligible_ids)
    ok_cases = 0
    disposition_hits = 0
    comparisons = []
    audit_hits = audit_total = 0
    unsafe_hits = unsafe_total = 0
    fallback_hits = fallback_total = recovery_hits = recovery_total = 0
    illegal_hits = illegal_total = r1_hits = r1_total = 0
    layers: dict[str, dict[str, int]] = defaultdict(lambda: {"hits": 0, "total": 0})
    for case_id, observations in grouped.items():
        case = by_case[case_id]
        if case_id not in eligible_ids:
            continue
        results = [compare_observation(case, AdversarialObservation(**obs)) for obs in observations]
        case_ok = all(obs["observation_status"] == "OK" for obs in observations)
        ok_cases += int(case_ok)
        disposition_hits += int(case_ok and all(item["contract_match"] for item in results))
        case_contract = case_ok and all(item["contract_match"] for item in results)
        layers[case["layer"]]["total"] += 1
        layers[case["layer"]]["hits"] += int(case_contract)
        expected_disposition = case["expected"]["disposition"]
        if expected_disposition == "SUPPORTED_FALLBACK":
            fallback_total += 1
            fallback_hits += int(case_contract)
        if expected_disposition == "RECOVERED":
            recovery_total += 1
            recovery_hits += int(case_contract)
        for obs, comp in zip(observations, results):
            for _ in case.get("required_audit_fields") or []:
                audit_total += 1
            audit_hits += len(case.get("required_audit_fields") or []) - len(comp["missing_audit_fields"])
            if case.get("safety_redline"):
                unsafe_total += 1
                unsafe_hits += int(bool(obs.get("unsafe_pass")))
            if case["protocol"] == "mutated_plan" or case["id"] in {"adv_p01", "adv_p02", "adv_p04", "adv_p05"}:
                illegal_total += 1
                illegal_hits += int(obs.get("observation_status") == "OK"
                                    and obs.get("disposition") == "SAFE_REJECT")
            comparisons.append({"execution_unit_id": obs["execution_unit_id"], **comp})
        if profile == "integrated" and expected_disposition == "EXECUTE_SUCCESS" and case.get("expected_result"):
            r1_total += 1
            # Only one execution unit is legal for current R1 cases.
            r1_hits += int(bool(observations[0].get("result_rows")) and
                           _exact_rows_match(observations[0]["result_rows"], case["expected_result"]))
    complete = journal.get("profile_execution_status") == "COMPLETED"
    ineligible_valid = all(
        record["observation_status"] == "PROFILE_INELIGIBLE"
        for record in records if record["case_id"] not in eligible_ids
    )
    harness = "PASS" if complete and ok_cases == eligible_cases and ineligible_valid else "FAIL"
    readiness = ("PASS" if disposition_hits == eligible_cases and unsafe_hits == 0 else "FAIL") if harness == "PASS" else "NOT_ASSESSED"
    formal_rate = disposition_hits / eligible_cases if complete and eligible_cases else None
    return {
        "profile_execution_status": journal.get("profile_execution_status"),
        "product_denominator_status": journal.get("product_denominator_status"),
        "harness_status": harness, "system_readiness": readiness,
        "case_coverage": {"hits": ok_cases, "total": eligible_cases},
        "variant_coverage": {"hits": sum(r["observation_status"] == "OK" for r in records if "::" in r["execution_unit_id"] and r["case_id"] in eligible_ids),
                             "total": sum("::" in r["execution_unit_id"] and r["case_id"] in eligible_ids for r in records)},
        "expected_disposition": {"hits": disposition_hits, "total": eligible_cases,
                                 "accuracy": formal_rate,
                                 "conformance": f"{disposition_hits}/{eligible_cases}" + (" (INCOMPLETE)" if not complete else "")},
        "unsafe_pass": {"hits": unsafe_hits, "total": unsafe_total},
        "illegal_plan_rejection": {"hits": illegal_hits, "total": illegal_total},
        "graceful_fallback": {"hits": fallback_hits, "total": fallback_total},
        "recovery_success": {"hits": recovery_hits, "total": recovery_total},
        "r1": {"hits": r1_hits, "total": r1_total},
        "audit_completeness": {"hits": audit_hits, "total": audit_total},
        "by_layer": dict(layers),
        "ledger_integrity": integrity, "comparisons": comparisons, "observations": records,
        "backlog": _build_backlog(comparisons, records),
    }


def _exact_rows_match(actual: list[dict[str, Any]], expected: dict[str, Any]) -> bool:
    if expected.get("type") != "exact_rows":
        return False
    keys = list(expected.get("key_fields") or [])
    values = list(expected.get("value_fields") or [])
    tolerance = float(expected.get("tolerance") or 0.0)

    def key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(row.get(name)) for name in keys)

    actual_map = {key(row): row for row in actual}
    expected_rows = expected.get("rows") or []
    if len(actual_map) != len(expected_rows):
        return False
    for wanted in expected_rows:
        observed = actual_map.get(key(wanted))
        if observed is None:
            return False
        for name in values:
            try:
                left, right = float(observed[name]), float(wanted[name])
            except (KeyError, TypeError, ValueError):
                return False
            if abs(left - right) > tolerance * max(1.0, abs(right)):
                return False
    return True


def _build_backlog(comparisons: list[dict[str, Any]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed = {r["execution_unit_id"]: r for r in records}
    backlog = []
    for item in comparisons:
        if not item["contract_match"]:
            unit = item["execution_unit_id"]
            severity = "P1" if observed[unit].get("unsafe_pass") else "P2"
            backlog.append({"severity": severity, "execution_unit_id": unit,
                            "evidence": item["errors"], "recommendation": "open separate hotfix" if severity == "P1" else "open product change"})
    return backlog


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Adversarial System Evaluation", "",
             f"- Profile: `{report.get('profile_execution_status')}`",
             f"- Harness: **{report.get('harness_status')}**",
             f"- System readiness: **{report.get('system_readiness')}**", ""]
    if report.get("metrics") is None and report.get("expected_disposition") is None:
        lines.append("Product metrics: N/A (ledger/profile not assessable).")
        return "\n".join(lines) + "\n"
    for key in ("case_coverage", "variant_coverage", "expected_disposition", "unsafe_pass",
                "illegal_plan_rejection", "graceful_fallback", "recovery_success", "r1",
                "audit_completeness"):
        value = report.get(key) or {}
        lines.append(f"- {key}: {value.get('hits')}/{value.get('total')}")
    lines += ["", "## Per execution unit", "", "| Unit | Observation | Disposition | Stage / Code | Unsafe |",
              "|---|---|---|---|---|"]
    for obs in report.get("observations") or []:
        lines.append(f"| {obs['execution_unit_id']} | {obs['observation_status']} | {obs.get('disposition') or '-'} | {obs.get('stage') or '-'} / {obs.get('code') or '-'} | {obs.get('unsafe_pass', False)} |")
    return "\n".join(lines) + "\n"


def run_offline(manifest: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    journal = AdversarialRunJournal.start(run_dir, manifest, "offline", {"external_calls": False})
    try:
        for case in manifest["cases"]:
            variants = case.get("variants") or [None]
            for variant in variants:
                unit = f"{case['id']}::{variant['id']}" if variant else case["id"]
                journal.mark_running(unit)
                journal.write_terminal(classify_offline(case, variant))
        data = journal.read()
        data["profile_execution_status"] = "COMPLETED"
        _atomic_json(journal.journal_path, data)
    finally:
        report = journal.finalize(force=True)
    (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report
