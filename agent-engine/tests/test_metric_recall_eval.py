from app.eval.metric_recall_eval import evaluate_metric_recall, scan_metric_recall


def _catalog():
    return [
        {"metricCode": "a", "metricName": "甲"},
        {"metricCode": "b", "metricName": "乙"},
        {"metricCode": "c", "metricName": "丙"},
    ]


def test_recall_denominator_excludes_cases_without_golden():
    cases = [
        {"id": "one", "question": "甲", "golden_spec": {"metrics": ["a"]}},
        {"id": "unknown", "question": "随便问", "golden_spec": None},
    ]
    report = evaluate_metric_recall(cases, _catalog(), configured_k=1, lexical_threshold=0.55)
    assert report["judged"] == 1
    assert report["unjudged"] == 1
    assert report["recall@configured_k"] == {"hits": 1, "total": 1, "rate": 1.0}


def test_configured_and_effective_recall_are_not_mixed():
    cases = [{"id": "multi", "question": "甲乙", "golden_spec": {"metrics": ["a", "b"]}}]
    report = evaluate_metric_recall(cases, _catalog(), configured_k=1, lexical_threshold=0.55)
    assert report["recall@configured_k"]["hits"] == 0
    assert report["strict_recall@effective_k"]["hits"] == 1
    assert report["effective_recall"]["hits"] == 1
    assert report["pinned_expansion_count"] == 1
    assert report["cases"][0]["effective_k"] == 2


def test_fallback_does_not_inflate_ranked_recall():
    cases = [{"id": "weak", "question": "天气", "golden_spec": {"metrics": ["c"]}}]
    report = evaluate_metric_recall(cases, _catalog(), configured_k=1, lexical_threshold=0.9)
    assert report["fallback_count"] == 1
    assert report["effective_recall"]["hits"] == 1
    assert report["strict_recall@effective_k"]["hits"] == 0
    assert report["gate_passed"] is False


def test_scan_preserves_each_parameter_combination():
    cases = [{"id": "one", "question": "甲", "golden_spec": {"metrics": ["a"]}}]
    reports = scan_metric_recall(cases, _catalog(), k_values=(1, 2), thresholds=(0.5,))
    assert [(x["configured_k"], x["lexical_threshold"]) for x in reports] == [(1, 0.5), (2, 0.5)]


def test_real_golden_recall_gate_is_49_of_49():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    cases = json.loads((root / "agent-engine/app/eval/cases.yaml").read_text())["cases"]
    catalog = json.loads((root / "src/main/resources/metric_catalog.json").read_text())
    report = evaluate_metric_recall(cases, catalog, configured_k=5, lexical_threshold=0.55)
    assert report["judged"] == 49
    assert report["unjudged"] == 12
    assert report["recall@configured_k"]["hits"] == 49
    assert report["strict_recall@effective_k"]["hits"] == 49
    assert report["effective_recall"]["hits"] == 49
    assert report["multi_metric_complete"] == {"hits": 2, "total": 2, "rate": 1.0}
    assert report["gate_passed"] is True
