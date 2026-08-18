"""Retriever：规范化 + 文本相似度 + 双阈值 + metrics 一致性校验。

- hit（≥0.95）→ 缓存直通（须过 catalog + metrics 一致性校验）
- inject（0.85~0.95）→ few-shot 注入
- miss → 现状
接口留向量演进位（未来 VectorRetriever 实现同一协议）。
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Any, Protocol

from app.memory.store import MemoryEntry

_HIT = "hit"
_INJECT = "inject"
_MISS = "miss"


@dataclass
class MemoryHit:
    entry: MemoryEntry
    score: float
    band: str  # "hit" | "inject"


class Retriever(Protocol):
    def search(self, question: str, limit: int = 3) -> list[MemoryHit]: ...


def normalize_question(question: str) -> str:
    """规范化：小写、去空白/全半角标点、折叠空格；保留数字（最近7天 vs 最近30天必须区分）。"""
    text = (question or "").lower().strip()
    # 全角转半角
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    # 去空白
    text = re.sub(r"\s+", "", text)
    # 去标点（保留字母数字）
    text = re.sub(r"[^\w\u4e00-\u9fff]+", "", text)
    return text


def extract_metric_names(question: str, catalog: list[dict[str, Any]]) -> list[str]:
    """从问题文本匹配 catalog 的 metricName（最长前缀），返回匹配到的 metricCode 列表。"""
    found: list[str] = []
    for m in catalog or []:
        name = str(m.get("metricName") or "")
        if name and name in question:
            found.append(str(m.get("metricCode")))
    return found


class TextSimilarityRetriever:
    """基于 difflib 字符级相似度（适合中文，零依赖、确定性）。"""

    def __init__(self, store, hit_threshold: float = 0.95,
                 inject_threshold: float = 0.85) -> None:
        self.store = store
        self.hit_threshold = hit_threshold
        self.inject_threshold = inject_threshold

    async def search(self, question: str, limit: int = 3, namespace: str = "default") -> list[MemoryHit]:
        norm = normalize_question(question)
        candidates: list[MemoryHit] = []
        for entry in await self.store.all(namespace):
            score = difflib.SequenceMatcher(None, norm, entry.norm_question).ratio()
            band = _MISS
            if score >= self.hit_threshold:
                band = _HIT
            elif score >= self.inject_threshold:
                band = _INJECT
            if band != _MISS:
                candidates.append(MemoryHit(entry=entry, score=score, band=band))
        # 相似度降序，同分按 hit_count 优先
        candidates.sort(key=lambda h: (h.score, h.entry.hit_count), reverse=True)
        return candidates[:limit]


def metrics_consistent(question: str, entry: MemoryEntry, catalog: list[dict[str, Any]]) -> bool:
    """metrics 一致性校验：问题文本匹配到的指标名必须与存储 metric_codes 一致。

    - 问题能匹配到指标名 且 与存储不一致 → 不一致（降级，防"点赞量"误命中"播放量"）
    - 问题匹配不到指标名（无法判定）→ 返回 False（降级 inject，不直通）
    """
    found = extract_metric_names(question, catalog)
    if not found:
        return False  # 无法判定 → 不直通（P2-3 收紧）
    stored = set(entry.metric_codes or [])
    return bool(found and set(found) == stored)


class HybridRetriever:
    """路径 B（P1 定死）：LanceDB 向量 search + FTS search 分开查，D4 公式自算融合。

    score = w·cos_norm + (1−w)·bm25_norm
    - cos_norm = max(0, cos)（cosine ∈ [-1,1] 裁剪到 [0,1]）
    - bm25_norm = bm25 / top1_bm25（候选集内相对分）
    embedding 不可用 → 降级 difflib（行为同 TextSimilarityRetriever，不打断主链路）。
    """

    def __init__(self, store, provider, hit_threshold: float = 0.95,
                 inject_threshold: float = 0.85, weight: float = 0.7) -> None:
        self.store = store
        self.provider = provider
        self.hit_threshold = hit_threshold
        self.inject_threshold = inject_threshold
        self.weight = weight

    async def search(self, question: str, limit: int = 3, namespace: str = "default") -> list[MemoryHit]:
        """返回非 miss 候选（hit/inject），分数降序。"""
        cands = await self._candidates(question, namespace)
        scored = [MemoryHit(entry=e, score=score, band=band) for e, score, band in cands if band != _MISS]
        scored.sort(key=lambda h: (h.score, h.entry.hit_count), reverse=True)
        return scored[:limit]

    async def best_score(self, question: str, namespace: str = "default") -> float:
        """原始融合分 top-1（含 miss 带，供阈值标定使用，不经过滤）。无候选返回 0.0。"""
        cands = await self._candidates(question, namespace)
        return max((score for _e, score, _band in cands), default=0.0)

    async def _candidates(self, question: str, namespace: str) -> list[tuple[Any, float, str]]:
        """路径 B 融合的原始候选（含 miss 带）：精确快路径 / 向量+FTS 自算 / difflib 降级。"""

        norm = normalize_question(question)
        # ① 精确匹配快路径（确定性契约：同问同答 100%，不依赖模型）
        entry = await self.store.find_by_question(norm, namespace)
        if entry is not None:
            return [(entry, 1.0, _HIT)]

        # ②③ 向量 + FTS 分开查
        vec = await self.provider.embed(question)
        if not vec:
            return await self._fallback_candidates(norm, namespace)

        k = max(10, 10)
        vec_hits = await self.store.search_by_vector(vec, namespace, k)
        fts_hits = await self.store.fts_search(norm, namespace, k)
        merged: dict[int, list] = {}
        for e, cos in vec_hits:
            merged[e.id] = [e, max(0.0, cos), 0.0]
        for e, bm25 in fts_hits:
            if e.id in merged:
                merged[e.id][2] = bm25
            else:
                merged[e.id] = [e, 0.0, bm25]

        top1_bm25 = max((v[2] for v in merged.values()), default=0.0)
        cands: list[tuple[Any, float, str]] = []
        for e, cos, bm25 in merged.values():
            cos_norm = cos  # 已裁剪
            bm25_norm = bm25 / top1_bm25 if top1_bm25 else 0.0
            score = self.weight * cos_norm + (1.0 - self.weight) * bm25_norm
            band = _MISS
            if score >= self.hit_threshold:
                band = _HIT
            elif score >= self.inject_threshold:
                band = _INJECT
            cands.append((e, score, band))
        cands.sort(key=lambda c: (c[1], c[0].hit_count), reverse=True)
        return cands

    async def _fallback_candidates(self, norm: str, namespace: str) -> list[tuple[Any, float, str]]:
        """embedding 不可用 → difflib 降级（与 TextSimilarityRetriever 同语义）。"""

        cands: list[tuple[Any, float, str]] = []
        for entry in await self.store.all(namespace):
            score = difflib.SequenceMatcher(None, norm, entry.norm_question).ratio()
            band = _MISS
            if score >= self.hit_threshold:
                band = _HIT
            elif score >= self.inject_threshold:
                band = _INJECT
            cands.append((entry, score, band))
        cands.sort(key=lambda c: (c[1], c[0].hit_count), reverse=True)
        return cands

    async def _fallback_text(self, norm: str, namespace: str, limit: int) -> list[MemoryHit]:
        """embedding 不可用 → difflib 降级（与 TextSimilarityRetriever 同语义）。"""
        candidates: list[MemoryHit] = []
        for entry in await self.store.all(namespace):
            score = difflib.SequenceMatcher(None, norm, entry.norm_question).ratio()
            band = _MISS
            if score >= self.hit_threshold:
                band = _HIT
            elif score >= self.inject_threshold:
                band = _INJECT
            if band != _MISS:
                candidates.append(MemoryHit(entry=entry, score=score, band=band))
        candidates.sort(key=lambda h: (h.score, h.entry.hit_count), reverse=True)
        return candidates[:limit]


def build_retriever(memory, provider=None) -> Retriever:
    """检索器工厂：lance 后端 + embedding 可用 → HybridRetriever；否则 TextSimilarityRetriever。"""
    from app.settings import settings

    if memory is not None and provider is not None and provider.available() \
            and getattr(settings, "memory_store_backend", "sqlite") == "lance":
        return HybridRetriever(
            memory, provider,
            settings.memory_hit_threshold, settings.memory_inject_threshold,
            getattr(settings, "memory_fusion_weight", 0.7))
    return TextSimilarityRetriever(
        memory, settings.memory_hit_threshold, settings.memory_inject_threshold)


def intent_acceptable(intent: dict) -> bool:
    """意图可接受性（与 nodes 判定一致）：有 metrics + intent 合法 + 置信度 ≥0.5。"""
    return bool(
        intent.get("metrics")
        and intent.get("intent") in {"aggregate", "trend", "ranking", "detail"}
        and float(intent.get("confidence") or 0.0) >= 0.5
    )


def hit_allowed(question: str, entry: MemoryEntry, catalog: list[dict[str, Any]]) -> bool:
    """运行时命中四重判定（nodes.py 与 runner band 分层共用的同一判定，零偏差承诺）：
    catalog 校验（口径未变）+ metrics 一致性（防"点赞量"误命中"播放量"）+ 意图可接受。
    """
    codes = {str(m.get("metricCode")) for m in catalog or []}
    if not all(code in codes for code in (entry.metric_codes or [])):
        return False
    if not metrics_consistent(question, entry, catalog):
        return False
    return intent_acceptable(entry.resolved_intent or {})
