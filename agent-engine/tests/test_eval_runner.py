import pytest

from app.eval import runner
from app.eval.runner import (
    _avg_tokens,
    aggregate,
    apply_run_config,
    compare_reports,
    error_result,
    render_report,
)
from app.settings import settings


def test_apply_run_config_llm_and_platform(monkeypatch):
    monkeypatch.setattr(settings, "eval_llm_mode", "mock")
    monkeypatch.setattr(settings, "platform_calls_enabled", False)
    cfg = apply_run_config(llm="real", platform="mock", cassette=None)

    assert cfg["llm"] == "real"
    assert cfg["platform"] == "mock"
    assert settings.eval_llm_mode == "real"
    assert settings.platform_calls_enabled is False


def test_apply_run_config_illegal_record_plus_real(monkeypatch):
    monkeypatch.setattr(settings, "eval_llm_mode", "mock")
    monkeypatch.setattr(settings, "platform_calls_enabled", False)
    with pytest.raises(SystemExit):
        apply_run_config(llm="record", platform="real", cassette=None)


def test_apply_run_config_replay_sets_cassette(monkeypatch):
    monkeypatch.setattr(settings, "eval_llm_mode", "replay")
    monkeypatch.setattr(settings, "platform_calls_enabled", False)
    cfg = apply_run_config(llm="replay", platform="mock", cassette="cassettes/ci.json")

    assert cfg["cassette"] == "cassettes/ci.json"
    assert settings.eval_llm_cassette == "cassettes/ci.json"


def test_error_result_marks_error():
    r = error_result({"id": "c9", "type": "open"}, TimeoutError("boom"))

    assert r["status"] == "ERROR"
    assert r["spec_score"] is None
    assert r["error"] is True
    assert "TimeoutError" in r["reason"]


def test_aggregate_excludes_error_from_judged():
    ok = {
        "id": "c1", "type": "text2sql", "passed": True, "status": "SUCCESS", "retry_count": 0,
        "latency_ms": 5, "sql_source": "synthesized",
        "spec_score": {
            "matched": True, "core_ok": True, "field_hits": 6, "field_total": 6,
            "fields": {"intent": True, "metrics": True, "dimensions": True,
                       "time_range": True, "filters": True, "ordering": True},
        },
    }
    err = {
        "id": "c2", "type": "text2sql", "passed": False, "status": "ERROR", "retry_count": 0,
        "latency_ms": 0, "sql_source": None, "spec_score": None, "error": True,
    }
    agg = aggregate([ok, err])

    assert agg["total"] == 2
    assert agg["evaluated"] == 1
    assert agg["error_count"] == 1
    assert agg["judged"] == 1
    assert agg["end_to_end"] == 1.0  # ERROR 不计入端到端分母
    assert agg["core_hits"] == 1


def test_render_report_headers_include_config_and_denominators():
    run_config = {"llm": "real", "platform": "mock", "model": "deepseek-chat", "eval_date": "2023-10-14", "cassette": "-"}
    md = render_report([], run_config, "2023-10-14")

    assert "LLM: `real`" in md
    assert "平台: `mock`" in md
    assert "评测可用性" in md
    assert "0/0" in md


def test_compare_reports_rejects_mismatched_config():
    cfg_a = {"llm": "real", "platform": "mock", "model": "m1", "eval_date": "2023-10-14"}
    cfg_b = {"llm": "real", "platform": "real", "model": "m1", "eval_date": "2023-10-14"}
    out = compare_reports({"config": cfg_a, "metrics": {}}, {"config": cfg_b, "metrics": {}})

    assert "拒绝对比" in out
    assert "platform" in out


def test_compare_reports_same_config_compares():
    cfg = {"llm": "real", "platform": "mock", "model": "m1", "eval_date": "2023-10-14"}
    a = {"config": cfg, "metrics": {"core_accuracy": 0.8, "end_to_end": 1.0}}
    b = {"config": cfg, "metrics": {"core_accuracy": 0.9, "end_to_end": 1.0}}
    out = compare_reports(a, b)

    assert "+10.00%" in out


@pytest.mark.asyncio
async def test_run_case_dispatches_real(monkeypatch):
    async def fake_real(case, eval_date):
        return {"id": case["id"], "platform": "real"}

    monkeypatch.setattr(runner, "run_real_case", fake_real)
    r = await runner.run_case({"id": "c"}, "real", "real", "2023-10-14")

    assert r["platform"] == "real"


@pytest.mark.asyncio
async def test_run_cases_isolates_errors(monkeypatch):
    async def boom(case, llm, platform, eval_date):
        raise RuntimeError("network down")

    monkeypatch.setattr(runner, "run_case", boom)
    results = await runner.run_cases([{"id": "c1"}, {"id": "c2"}], "real", "mock", "2023-10-14")

    assert len(results) == 2
    assert all(r["status"] == "ERROR" for r in results)


def test_golden_metrics_covered_by_metric_catalog():
    import json

    from app.eval.runner import DEFAULT_CASES, ROOT

    cases = json.loads(DEFAULT_CASES.read_text(encoding="utf-8"))
    golden_metrics = set()
    for c in cases["cases"]:
        g = c.get("golden_spec")
        if g:
            golden_metrics.update(g.get("metrics") or [])

    catalog = json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text(encoding="utf-8"))
    catalog_codes = {m["metricCode"] for m in catalog}

    assert golden_metrics <= catalog_codes, f"missing: {golden_metrics - catalog_codes}"


class _FakeAnalyzeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_run_real_case_parses_observability(monkeypatch):
    payload = {
        "status": "WAITING_APPROVAL",
        "summary": "Analysis is waiting for human approval before running high-risk SQL. Reason: SQL_LARGE_SCAN",
        "period": "-",
        "recommendations": ["Review the SQL risk reason and approve or reject this run."],
        "debug": {
            "resolvedIntent": {
                "intent": "aggregate",
                "metrics": ["total_plays"],
                "dimensions": [],
                "time_range": {"type": "none", "granularity": None},
                "filters": [],
                "ordering": None,
            },
            "sqlRetryCount": 0,
            "sqlSource": "semantic",
        },
    }

    async def fake_get(client, question):
        return _FakeAnalyzeResponse(payload)

    monkeypatch.setattr(runner, "_get_analyze", fake_get)
    case = {
        "id": "c18_detail_playback",
        "type": "risk",
        "question": "查询所有播放明细",
        "expected_status": "WAITING_APPROVAL",
        "golden_spec": {
            "intent": "aggregate",
            "metrics": ["total_plays"],
            "dimensions": [],
            "time_range": {"type": "none", "granularity": None},
            "filters": [],
            "ordering": None,
        },
    }

    r = await runner.run_real_case(case, "2023-10-14")

    assert r["status"] == "WAITING_APPROVAL"
    assert r["sql_source"] == "semantic"
    assert r["passed"] is True
    assert r["spec_score"]["core_ok"] is True

def test_avg_tokens():
    assert _avg_tokens([]) == 0.0
    assert _avg_tokens([{"tokens": 10}, {"tokens": 30}]) == 20.0
    assert _avg_tokens([{"tokens": 0}]) == 0.0
