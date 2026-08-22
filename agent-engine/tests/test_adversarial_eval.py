from __future__ import annotations

import copy

import httpx
import pytest

from app.eval.adversarial import (
    AdversarialObservation,
    ManifestError,
    build_registry,
    classify_offline,
    compare_observation,
    execute_question,
    load_manifest,
    run_g04_worker,
    validate_manifest,
)


def test_manifest_has_exact_versioned_four_by_five_matrix():
    manifest = load_manifest()
    assert len(manifest["cases"]) == 20
    assert len(build_registry(manifest, "offline")) == 22
    assert {c["layer"] for c in manifest["cases"]} == {
        "semantic", "planning", "synthesis", "safety_recovery",
    }


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "layer_count", "enum", "state"])
def test_manifest_fails_fast_before_product_execution(mutation):
    manifest = copy.deepcopy(load_manifest())
    if mutation == "missing":
        del manifest["cases"][0]["expected"]["stage"]
    elif mutation == "duplicate":
        manifest["cases"][1]["id"] = manifest["cases"][0]["id"]
    elif mutation == "layer_count":
        manifest["cases"][0]["layer"] = "planning"
    elif mutation == "enum":
        manifest["cases"][0]["expected"]["disposition"] = "MAGIC"
    else:
        manifest["cases"][0]["protocol"] = "arbitrary_callback"
    with pytest.raises(ManifestError):
        validate_manifest(manifest)


def test_non_ok_observation_cannot_claim_product_disposition():
    with pytest.raises(ValueError, match="only OK"):
        AdversarialObservation("u", "c", "semantic", "question", "ADAPTER_ERROR",
                               disposition="SYSTEM_ERROR")


def test_c_truth_contract_is_manual_and_never_self_confirming():
    cases = {c["id"]: c for c in load_manifest()["cases"]}
    for case_id in ("adv_c01", "adv_c02", "adv_c03", "adv_c04"):
        truth = cases[case_id]["truth_source"]
        assert truth["type"] == "manual_sql"
        assert truth["generated_by"] == "independent_manual_sql"
        assert truth["sql"].lstrip().upper().startswith("SELECT")
        assert "query_time" in truth and "dataset_version" in truth
    for case in cases.values():
        if case["expected"]["disposition"] != "EXECUTE_SUCCESS":
            assert "expected_result" not in case


def test_p05_three_variants_report_real_validator_unsafe_pass():
    case = next(c for c in load_manifest()["cases"] if c["id"] == "adv_p05")
    observations = [classify_offline(case, variant) for variant in case["variants"]]
    assert [o.execution_unit_id for o in observations] == [
        "adv_p05::lineage", "adv_p05::metric", "adv_p05::schema",
    ]
    assert all(o.audit["oracle_mismatch"] for o in observations)
    # Current product only compares declared version + canonical candidates; the
    # harness honestly exposes rather than fixes this P1.
    assert all(o.observation_status == "OK" for o in observations)
    assert all(o.disposition == "SYSTEM_ERROR" for o in observations)
    assert all(o.unsafe_pass for o in observations)
    assert all(o.audit["compiler_invocation_attempted"] for o in observations)


def test_g04_isolated_worker_uses_fixed_retry_contract(monkeypatch):
    monkeypatch.setenv("LINEAGE_MAX_RETRIES", "99")
    result = run_g04_worker()
    assert result["observation_status"] == "OK"
    assert result["effective_lineage_max_retries"] == 1
    assert result["planning_retry_count"] == 2
    assert result["fallback_reason"] == "PLANNER_RETRY_EXHAUSTED"
    assert result["node_counts"] == {"PLAN_SELECT": 2, "PLAN_VALIDATE": 2}
    assert result["compiler_invocation_attempted"] is False
    assert result["worker_reaped"] is True


def test_comparator_separates_contract_and_audit():
    case = next(c for c in load_manifest()["cases"] if c["id"] == "adv_c05")
    obs = classify_offline(case)
    obs.audit.pop("synthesis_error_reason")
    compared = compare_observation(case, obs)
    assert compared["disposition_match"] is True
    assert compared["audit_complete"] is False
    assert "synthesis_error_reason" in compared["missing_audit_fields"]


@pytest.mark.asyncio
async def test_question_http_500_is_product_error_not_harness_failure(monkeypatch):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **_kwargs):
            request = httpx.Request("GET", url)
            response = httpx.Response(500, request=request, text="product failed")
            raise httpx.HTTPStatusError("server error", request=request, response=response)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    case = next(c for c in load_manifest()["cases"] if c["id"] == "adv_s01")
    observation = await execute_question(case)
    assert observation.observation_status == "OK"
    assert observation.disposition == "SYSTEM_ERROR"
    assert observation.code == "HTTP_500"
