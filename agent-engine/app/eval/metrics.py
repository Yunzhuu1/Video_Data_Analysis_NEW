from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetricResult:
    name: str
    passed: int
    total: int

    @property
    def score(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total


def contains_all(text: str, expected: list[str]) -> bool:
    lowered = text.lower()
    return all(item.lower() in lowered for item in expected)


def required_fields_present(payload: dict[str, Any], fields: list[str]) -> bool:
    return all(field in payload and payload[field] not in (None, "", []) for field in fields)


def summarize_results(case_results: list[dict[str, Any]]) -> list[MetricResult]:
    totals: dict[str, list[int]] = {}
    for result in case_results:
        metric_name = str(result["type"])
        passed, total = totals.setdefault(metric_name, [0, 0])
        totals[metric_name] = [passed + int(bool(result["passed"])), total + 1]

    overall_passed = sum(1 for result in case_results if result["passed"])
    metrics = [MetricResult("overall", overall_passed, len(case_results))]
    metrics.extend(
        MetricResult(name, passed_total[0], passed_total[1])
        for name, passed_total in sorted(totals.items())
    )
    return metrics
