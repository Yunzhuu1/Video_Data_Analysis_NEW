from pathlib import Path

from app.eval.lineage_eval import evaluate_lineage, load_lineage_cases


def test_lineage_offline_hard_gates():
    path = Path(__file__).resolve().parents[1] / "app/eval/lineage_cases.yaml"
    report = evaluate_lineage(load_lineage_cases(path))
    assert report["path_recall"] == {"hits": 8, "total": 8, "rate": 1.0}
    assert report["expected_rejection"] == {"hits": 2, "total": 2, "rate": 1.0}
    assert report["plan_selection_accuracy"]["hits"] == 2
    assert report["illegal_plan_rejection"] == {"hits": 1, "total": 1}
    assert report["replan_success"] == {"hits": 1, "total": 1}
