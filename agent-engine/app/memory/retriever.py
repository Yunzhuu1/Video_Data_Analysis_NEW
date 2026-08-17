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
