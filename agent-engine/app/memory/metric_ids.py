"""MetricIdFingerprint：指标 ID 表达指纹（catalog + 沉淀表达 → 每 ID 表达集）。

- 相似度定义（P2-2 写死）：embedding cosine（provider 注入）；embedding 不可用降级 difflib。
- 用途：读取侧候选 ID 判定（可选增强，默认 `MEMORY_ALIAS_FINGERPRINT=0` 关闭）。
- 与混合检索重叠（P2-4）：检索 top-N 受 namespace/沉淀状态影响；指纹是 catalog+沉淀的稳定 ID 视角。
"""
from __future__ import annotations

import difflib
from typing import Any

from app.memory.retriever import normalize_question

DEFAULT_FINGERPRINT_THRESHOLD = 0.6  # 比直通阈值宽，只做候选判定（标定后校准）
DEFAULT_TOP_K = 20  # 每 ID 表达集上限，防"播放"泛化误归


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class MetricIdFingerprint:
    def __init__(self, catalog: list[dict[str, Any]], entries: list[Any] | None = None,
                 provider=None, top_k: int = DEFAULT_TOP_K,
                 threshold: float = DEFAULT_FINGERPRINT_THRESHOLD) -> None:
        self.provider = provider
        self.top_k = top_k
        self.threshold = threshold
        self._phrases: dict[str, list[str]] = {}
        self._vecs: dict[str, list[list[float]]] = {}
        self._difflib = provider is None or not getattr(provider, "available", lambda: False)()
        self.build(catalog, entries or [])

    def build(self, catalog: list[dict[str, Any]], entries: list[Any]) -> None:
        """每 ID 表达集：catalog.metricName + 沉淀条目 norm_question（按 metric_codes 归属），top_k 截断。"""
        counts: dict[str, list[str]] = {}
        for m in catalog or []:
            code = str(m.get("metricCode") or "")
            name = str(m.get("metricName") or "")
            if code and name:
                counts.setdefault(code, []).append(name)
        for e in entries:
            for code in (e.metric_codes or []):
                q = normalize_question(str(getattr(e, "norm_question", "")))
                if q:
                    counts.setdefault(str(code), []).append(q)
        self._phrases = {code: phrases[: self.top_k] for code, phrases in counts.items()}

    async def _embed_all(self) -> None:
        if self._vecs or self._difflib or self.provider is None:
            return
        for code, phrases in self._phrases.items():
            vecs: list[list[float]] = []
            for ph in phrases:
                v = await self.provider.embed(ph)
                if v:
                    vecs.append(v)
            self._vecs[code] = vecs

    async def candidate_ids(self, question: str) -> list[str]:
        """问题 → 候选 metric ID 列表（精确名已在别名层处理；指纹兜底动态表达）。"""
        q = normalize_question(question)
        await self._embed_all()
        if self._vecs:
            qv = await self.provider.embed(q) if self.provider else None
            if qv:
                scored = [(code, max(_cosine(qv, v) for v in vecs))
                          for code, vecs in self._vecs.items() if vecs]
                return [code for code, s in sorted(scored, key=lambda x: x[1], reverse=True)
                        if s >= self.threshold]
        # 降级：difflib 字符相似度（确定性，行为不劣于现状）
        scored = []
        for code, phrases in self._phrases.items():
            s = max(difflib.SequenceMatcher(None, q, ph).ratio() for ph in phrases)
            scored.append((code, s))
        return [code for code, s in sorted(scored, key=lambda x: x[1], reverse=True)
                if s >= self.threshold]
