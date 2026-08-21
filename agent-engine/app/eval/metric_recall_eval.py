"""指标候选召回的离线门禁：不调用 LLM、embedding 或数据库。"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.memory.aliases import get_aliases
from app.semantic.metric_recall import MetricCandidateRetriever


def evaluate_metric_recall(
    cases: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    *,
    configured_k: int,
    lexical_threshold: float,
    alias_loader: Callable[[], dict[str, str]] = get_aliases,
) -> dict[str, Any]:
    judged = [case for case in cases if (case.get("golden_spec") or {}).get("metrics")]
    details: list[dict[str, Any]] = []
    configured_hits = 0
    strict_hits = 0
    effective_hits = 0
    multi_total = 0
    multi_hits = 0
    fallback_reasons: dict[str, int] = {}
    pinned_expansion_count = 0

    retriever = MetricCandidateRetriever(
        top_k=configured_k,
        lexical_threshold=lexical_threshold,
        mode="topk",
        alias_loader=alias_loader,
    )
    for case in judged:
        result = retriever.retrieve(str(case.get("question") or ""), catalog)
        golden = {str(x) for x in case["golden_spec"]["metrics"]}
        configured_candidates = [
            item.metric_code for item in result.ranked_candidates[:configured_k]
        ]
        strict_candidates = [
            item.metric_code for item in result.ranked_candidates[:result.effective_k]
        ]
        prompt_candidates = result.prompt_catalog_codes
        configured_ok = golden <= set(configured_candidates)
        strict_ok = golden <= set(strict_candidates)
        effective_ok = golden <= set(prompt_candidates)
        configured_hits += int(configured_ok)
        strict_hits += int(strict_ok)
        effective_hits += int(effective_ok)
        if len(golden) >= 2:
            multi_total += 1
            multi_hits += int(strict_ok)
        if result.pinned_count > configured_k:
            pinned_expansion_count += 1
        if result.fallback:
            reason = result.fallback_reason or "unknown"
            fallback_reasons[reason] = fallback_reasons.get(reason, 0) + 1
        details.append({
            "id": case["id"],
            "golden_metrics": sorted(golden),
            "mode": result.mode,
            "fallback": result.fallback,
            "fallback_reason": result.fallback_reason,
            "configured_k": configured_k,
            "pinned_count": result.pinned_count,
            "effective_k": result.effective_k,
            "configured_candidates": configured_candidates,
            "effective_candidates": strict_candidates,
            "prompt_catalog_codes": prompt_candidates,
            "configured_ok": configured_ok,
            "strict_ok": strict_ok,
            "effective_ok": effective_ok,
        })

    denominator = len(judged)
    return {
        "judged": denominator,
        "unjudged": len(cases) - denominator,
        "configured_k": configured_k,
        "lexical_threshold": lexical_threshold,
        "recall@configured_k": {"hits": configured_hits, "total": denominator,
                                  "rate": configured_hits / denominator if denominator else 0.0},
        "strict_recall@effective_k": {"hits": strict_hits, "total": denominator,
                                       "rate": strict_hits / denominator if denominator else 0.0},
        "effective_recall": {"hits": effective_hits, "total": denominator,
                             "rate": effective_hits / denominator if denominator else 0.0},
        "multi_metric_complete": {"hits": multi_hits, "total": multi_total,
                                  "rate": multi_hits / multi_total if multi_total else 0.0},
        "pinned_expansion_count": pinned_expansion_count,
        "fallback_count": sum(fallback_reasons.values()),
        "fallback_reasons": fallback_reasons,
        "gate_passed": strict_hits == denominator and effective_hits == denominator,
        "failures": [item for item in details if not item["strict_ok"] or not item["effective_ok"]],
        "cases": details,
    }


def scan_metric_recall(
    cases: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    *,
    k_values: tuple[int, ...] = (5, 8, 15),
    thresholds: tuple[float, ...] = (0.55, 0.45, 0.35),
    alias_loader: Callable[[], dict[str, str]] = get_aliases,
) -> list[dict[str, Any]]:
    """按设计顺序扫描参数；调用方选择首个 gate_passed 组合并如实保留全表。"""
    return [
        evaluate_metric_recall(
            cases,
            catalog,
            configured_k=k,
            lexical_threshold=threshold,
            alias_loader=alias_loader,
        )
        for k in k_values
        for threshold in thresholds
    ]
