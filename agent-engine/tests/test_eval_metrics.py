from app.eval.metrics import contains_all, required_fields_present, summarize_results


def test_contains_all_is_case_insensitive():
    assert contains_all("SELECT total_plays FROM metric_daily", ["select", "TOTAL_PLAYS"])


def test_required_fields_present_rejects_empty_values():
    assert required_fields_present({"summary": "ok", "recommendations": ["x"]}, ["summary", "recommendations"])
    assert not required_fields_present({"summary": "", "recommendations": []}, ["summary", "recommendations"])


def test_summarize_results_groups_by_type():
    metrics = summarize_results(
        [
            {"type": "text2sql", "passed": True},
            {"type": "text2sql", "passed": False},
            {"type": "rag", "passed": True},
        ]
    )

    by_name = {metric.name: metric for metric in metrics}
    assert by_name["overall"].score == 2 / 3
    assert by_name["text2sql"].score == 0.5
    assert by_name["rag"].score == 1.0
