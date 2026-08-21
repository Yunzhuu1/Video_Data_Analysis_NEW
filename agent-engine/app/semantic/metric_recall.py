"""无 embedding 依赖的确定性指标候选召回。"""
from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from app.memory.aliases import get_aliases

RecallMode = Literal["topk", "full", "full_fallback"]


def normalize_metric_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    return "".join(char for char in normalized if char.isalnum())


def _ngrams(value: str, size: int) -> set[str]:
    if size <= 0 or len(value) < size:
        return set()
    return {value[index:index + size] for index in range(len(value) - size + 1)}


def lexical_coverage(expression: str, question: str) -> float:
    """表达 n-gram 被问题覆盖的比例；表达为空时为 0，单字符只算 unigram。"""
    expression = normalize_metric_text(expression)
    question = normalize_metric_text(question)
    if not expression or not question:
        return 0.0
    unigram = _ngrams(expression, 1)
    q_unigram = _ngrams(question, 1)
    unigram_score = len(unigram & q_unigram) / len(unigram)
    if len(expression) == 1:
        return unigram_score
    bigram = _ngrams(expression, 2)
    q_bigram = _ngrams(question, 2)
    bigram_score = len(bigram & q_bigram) / len(bigram)
    return 0.35 * unigram_score + 0.65 * bigram_score


@dataclass(frozen=True)
class MetricCandidate:
    metric_code: str
    score: float
    reasons: tuple[str, ...] = ()
    matched_expressions: tuple[str, ...] = ()
    pinned: bool = False

    def debug_dict(self) -> dict[str, Any]:
        return {
            "metricCode": self.metric_code,
            "score": round(self.score, 6),
            "reasons": list(self.reasons),
            "matchedExpressions": list(self.matched_expressions),
            "pinned": self.pinned,
        }


@dataclass(frozen=True)
class MetricRecallResult:
    ranked_candidates: list[MetricCandidate]
    prompt_catalog: list[dict[str, Any]]
    mode: RecallMode
    fallback: bool
    fallback_reason: str | None
    configured_k: int
    pinned_count: int
    effective_k: int
    lexical_threshold: float
    full_catalog_count: int
    prompt_catalog_count: int
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def prompt_catalog_codes(self) -> list[str]:
        return [str(metric.get("metricCode") or "") for metric in self.prompt_catalog]


@dataclass(frozen=True)
class _Expression:
    text: str
    normalized: str
    metric_code: str
    source: str


class MetricCandidateRetriever:
    def __init__(
        self,
        top_k: int = 5,
        lexical_threshold: float = 0.55,
        mode: str = "topk",
        alias_loader: Callable[[], dict[str, str]] = get_aliases,
    ) -> None:
        self.top_k = max(1, int(top_k))
        self.lexical_threshold = float(lexical_threshold)
        self.mode = mode
        self.alias_loader = alias_loader

    def retrieve(self, question: str, catalog: list[dict[str, Any]]) -> MetricRecallResult:
        full_catalog = list(catalog or [])
        if self.mode == "full":
            return self._full_result(full_catalog)
        if self.mode != "topk":
            return self._fallback(full_catalog, "retriever_error", f"invalid mode: {self.mode}")
        try:
            return self._retrieve_topk(question, full_catalog, self.alias_loader())
        except Exception as exc:  # noqa: BLE001 - 召回失败必须回退完整目录
            return self._fallback(full_catalog, "retriever_error", str(exc))

    def _retrieve_topk(
        self,
        question: str,
        catalog: list[dict[str, Any]],
        aliases: dict[str, str],
    ) -> MetricRecallResult:
        codes = [str(item.get("metricCode") or "").strip() for item in catalog]
        if not catalog or any(not code for code in codes) or len(set(codes)) != len(codes):
            return self._fallback(catalog, "invalid_catalog", "catalog metricCode invalid")
        by_code = {code: item for code, item in zip(codes, catalog)}
        expressions: list[_Expression] = []
        for code, item in by_code.items():
            expressions.extend(self._valid_expressions([
                (code, code, "metric_code"),
                (str(item.get("metricName") or ""), code, "metric_name"),
            ]))
        expressions.extend(self._valid_expressions([
            (alias, code, "alias") for alias, code in aliases.items() if code in by_code
        ]))

        normalized_question = normalize_metric_text(question)
        pinned_matches = self._longest_matches(normalized_question, expressions)
        pinned_by_code: dict[str, list[_Expression]] = {}
        for expression in pinned_matches:
            pinned_by_code.setdefault(expression.metric_code, []).append(expression)

        candidates: list[MetricCandidate] = []
        for code in codes:
            metric_expressions = [x for x in expressions if x.metric_code == code]
            scored = [(lexical_coverage(x.normalized, normalized_question), x)
                      for x in metric_expressions]
            score = max((item[0] for item in scored), default=0.0)
            pinned = pinned_by_code.get(code, [])
            matched = tuple(dict.fromkeys(x.text for x in pinned))
            reasons = tuple(dict.fromkeys(f"exact:{x.source}" for x in pinned))
            if score > 0:
                reasons += ("lexical",)
            candidates.append(MetricCandidate(code, score, reasons, matched, bool(pinned)))

        candidates.sort(key=lambda item: (not item.pinned, -item.score, item.metric_code))
        pinned_count = sum(1 for item in candidates if item.pinned)
        effective_k = max(self.top_k, pinned_count)
        ranked = candidates[:effective_k]
        top_score = candidates[0].score if candidates else 0.0
        if pinned_count == 0 and top_score < self.lexical_threshold:
            return self._fallback(
                catalog,
                "no_reliable_signal",
                None,
                ranked=ranked,
                pinned_count=pinned_count,
                effective_k=effective_k,
            )
        prompt_codes = {item.metric_code for item in ranked}
        prompt_catalog = [item for item in catalog if str(item.get("metricCode")) in prompt_codes]
        # Prompt 顺序与 ranked 一致，而不是依赖 catalog 原始顺序。
        prompt_catalog.sort(key=lambda item: next(
            i for i, candidate in enumerate(ranked)
            if candidate.metric_code == str(item.get("metricCode"))
        ))
        return MetricRecallResult(
            ranked_candidates=ranked,
            prompt_catalog=prompt_catalog,
            mode="topk",
            fallback=False,
            fallback_reason=None,
            configured_k=self.top_k,
            pinned_count=pinned_count,
            effective_k=effective_k,
            lexical_threshold=self.lexical_threshold,
            full_catalog_count=len(catalog),
            prompt_catalog_count=len(prompt_catalog),
        )

    @staticmethod
    def _valid_expressions(raw: list[tuple[str, str, str]]) -> list[_Expression]:
        result = []
        for text, code, source in raw:
            normalized = normalize_metric_text(text)
            if normalized:
                result.append(_Expression(text, normalized, code, source))
        return result

    @staticmethod
    def _longest_matches(question: str, expressions: list[_Expression]) -> list[_Expression]:
        remaining = question
        source_order = {"metric_name": 0, "metric_code": 1, "alias": 2}
        ordered = sorted(
            expressions,
            key=lambda x: (-len(x.normalized), source_order.get(x.source, 9), x.text, x.metric_code),
        )
        found: list[_Expression] = []
        for expression in ordered:
            if expression.normalized in remaining:
                found.append(expression)
                remaining = remaining.replace(expression.normalized, "", 1)
        return found

    def _full_result(self, catalog: list[dict[str, Any]]) -> MetricRecallResult:
        return MetricRecallResult(
            ranked_candidates=[], prompt_catalog=catalog, mode="full", fallback=False,
            fallback_reason=None, configured_k=self.top_k, pinned_count=0,
            effective_k=self.top_k, lexical_threshold=self.lexical_threshold,
            full_catalog_count=len(catalog), prompt_catalog_count=len(catalog),
        )

    def _fallback(
        self,
        catalog: list[dict[str, Any]],
        reason: str,
        warning: str | None,
        ranked: list[MetricCandidate] | None = None,
        pinned_count: int = 0,
        effective_k: int | None = None,
    ) -> MetricRecallResult:
        warnings = (warning,) if warning else ()
        return MetricRecallResult(
            ranked_candidates=ranked or [], prompt_catalog=catalog, mode="full_fallback",
            fallback=True, fallback_reason=reason, configured_k=self.top_k,
            pinned_count=pinned_count, effective_k=effective_k or self.top_k,
            lexical_threshold=self.lexical_threshold, full_catalog_count=len(catalog),
            prompt_catalog_count=len(catalog), warnings=warnings,
        )
