import pytest

from app.semantic.metric_recall import (
    MetricCandidateRetriever,
    lexical_coverage,
    normalize_metric_text,
)


def _catalog(*items):
    return [{"metricCode": code, "metricName": name, "businessDefinition": ""}
            for code, name in items]


def test_normalization_and_ngram_boundaries():
    assert normalize_metric_text(" Total_Plays！ ") == "totalplays"
    assert normalize_metric_text("，！") == ""
    assert lexical_coverage("量", "最近播放量") == 1.0
    assert lexical_coverage("", "播放量") == 0.0
    assert lexical_coverage("播放量", "最近7天各分类播放量是多少") == 1.0


def test_exact_metric_name_and_alias_are_pinned():
    catalog = _catalog(("total_plays", "播放量"), ("total_likes", "点赞量"),
                       ("completion_rate", "完播率"))
    result = MetricCandidateRetriever(top_k=2, alias_loader=lambda: {"点赞数": "total_likes"}) \
        .retrieve("播放量和点赞数", catalog)
    assert result.mode == "topk"
    assert result.pinned_count == 2
    assert [x.metric_code for x in result.ranked_candidates] == ["total_likes", "total_plays"]
    assert set(result.prompt_catalog_codes) == {"total_plays", "total_likes"}


def test_longest_match_prevents_overlapping_short_metric():
    catalog = _catalog(("plays", "播放"), ("duration", "播放时长"))
    result = MetricCandidateRetriever(top_k=1, alias_loader=dict).retrieve("播放时长", catalog)
    assert result.pinned_count == 1
    assert result.ranked_candidates[0].metric_code == "duration"


def test_same_length_normalized_conflict_uses_metric_code_order():
    catalog = _catalog(("z_metric", "Ａ量"), ("a_metric", "A量"))
    result = MetricCandidateRetriever(top_k=1, alias_loader=dict).retrieve("A量", catalog)
    assert result.pinned_count == 1
    assert result.ranked_candidates[0].metric_code == "a_metric"


def test_pinned_count_expands_effective_k_without_truncation():
    catalog = _catalog(("a", "甲"), ("b", "乙"), ("c", "丙"))
    result = MetricCandidateRetriever(top_k=2, alias_loader=dict).retrieve("甲乙丙", catalog)
    assert result.configured_k == 2
    assert result.pinned_count == result.effective_k == 3
    assert {x.metric_code for x in result.ranked_candidates} == {"a", "b", "c"}


def test_result_is_stably_sorted():
    catalog = _catalog(("b", "乙"), ("a", "甲"), ("c", "丙"))
    retriever = MetricCandidateRetriever(top_k=3, lexical_threshold=0, alias_loader=dict)
    first = retriever.retrieve("无关", catalog)
    second = retriever.retrieve("无关", catalog)
    assert first == second
    assert [x.metric_code for x in first.ranked_candidates] == ["a", "b", "c"]


def test_low_signal_falls_back_but_keeps_ranked_candidates():
    catalog = _catalog(("total_plays", "播放量"), ("total_likes", "点赞量"))
    result = MetricCandidateRetriever(top_k=1, lexical_threshold=0.8,
                                      alias_loader=dict).retrieve("天气如何", catalog)
    assert result.mode == "full_fallback"
    assert result.fallback is True
    assert result.fallback_reason == "no_reliable_signal"
    assert result.prompt_catalog == catalog
    assert len(result.ranked_candidates) == 1


def test_full_mode_is_not_fallback():
    catalog = _catalog(("total_plays", "播放量"))
    result = MetricCandidateRetriever(mode="full", alias_loader=dict).retrieve("x", catalog)
    assert result.mode == "full"
    assert result.fallback is False
    assert result.fallback_reason is None
    assert result.prompt_catalog == catalog


@pytest.mark.parametrize("catalog", [[], [{"metricCode": "", "metricName": "坏数据"}]])
def test_invalid_catalog_falls_back(catalog):
    result = MetricCandidateRetriever(alias_loader=dict).retrieve("播放量", catalog)
    assert result.mode == "full_fallback"
    assert result.fallback_reason == "invalid_catalog"


def test_loader_error_falls_back_without_embedding_or_network():
    def broken_loader():
        raise RuntimeError("bad aliases")

    catalog = _catalog(("total_plays", "播放量"))
    result = MetricCandidateRetriever(alias_loader=broken_loader).retrieve("播放量", catalog)
    assert result.mode == "full_fallback"
    assert result.fallback_reason == "retriever_error"
    assert result.warnings == ("bad aliases",)


def test_alias_referencing_unknown_metric_invalidates_recall_resource():
    catalog = _catalog(("total_plays", "播放量"))
    result = MetricCandidateRetriever(
        alias_loader=lambda: {"点赞数": "total_like_typo"},
    ).retrieve("点赞数", catalog)
    assert result.mode == "full_fallback"
    assert result.fallback_reason == "invalid_catalog"
    assert result.prompt_catalog == catalog
    assert "unknown metricCode" in result.warnings[0]
