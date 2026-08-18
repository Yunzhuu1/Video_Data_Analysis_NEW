"""阈值标定脚本（memory-hybrid-retrieval 任务 0.2/2.2）。

路径 B：LanceDB 向量 search + FTS search 分开查，D4 公式自算融合（score = w·cos_norm + (1−w)·bm25_norm）。
用【真实方舟 API】跑同义集 / 近重复分布，输出建议 hit/inject 阈值与 w。

用法（需 ARK_API_KEY + 已开通模型）：
    cd agent-engine && .venv/bin/python -m app.eval.calibrate_thresholds --w 0.7
"""
from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from app.eval.runner import DEFAULT_CASES, load_cases
from app.memory.embeddings import get_embedding_provider
from app.memory.retriever import HybridRetriever, normalize_question
from app.memory.vector_store import LanceVectorStore
from app.settings import settings

_SYNONYM = Path(__file__).parent / "synonym_cases.yaml"


async def _calibrate(provider, w: float, hit_t: float, inject_t: float) -> dict:
    """核心标定（可测）：seed 8 个 source cases → 对每条同义/近重复/毒化计算原始融合分。"""
    _date, golden = load_cases(DEFAULT_CASES)
    source_by_id = {c["id"]: c for c in golden if c.get("golden_spec")}
    syn_data = json.loads(_SYNONYM.read_text(encoding="utf-8"))["cases"]

    tmp = tempfile.mkdtemp(prefix="calib-")
    store = LanceVectorStore(tmp, provider=provider, embedding_model=settings.ark_embedding_model)
    await store.init()
    try:
        seen: set[str] = set()
        for s in syn_data:
            src = source_by_id[s["source_case"]]
            if src["id"] in seen:
                continue
            seen.add(src["id"])
            g = src["golden_spec"]
            intent = {**g, "confidence": 0.9}
            await store.upsert(normalize_question(src["question"]), intent,
                               list(g.get("metrics") or []), "h", namespace="calib")
        # 额外毒化 seed（播放量条目，供毒化对照）
        await store.upsert("最近7天播放量是多少",
                           {"intent": "trend", "metrics": ["total_plays"], "confidence": 0.9},
                           ["total_plays"], "h", namespace="calib")

        retriever = HybridRetriever(store, provider, hit_threshold=hit_t, inject_threshold=inject_t, weight=w)

        def _band(score: float) -> str:
            if score >= hit_t:
                return "hit"
            if score >= inject_t:
                return "inject"
            return "miss"

        rows = []
        for s in syn_data:
            score = await retriever.best_score(s["question"], namespace="calib")
            rows.append({"id": s["id"], "question": s["question"],
                         "score": round(score, 4), "band": _band(score)})
        near_q = "统计各分类总播放量啊"
        near_score = await retriever.best_score(near_q, namespace="calib")
        poison_score = await retriever.best_score("最近7天点赞量是多少", namespace="calib")
        return {
            "w": w, "hit_t": hit_t, "inject_t": inject_t,
            "rows": rows, "near_score": round(near_score, 4), "poison_score": round(poison_score, 4),
        }
    finally:
        await store.close()


async def run(w: float, hit_t: float, inject_t: float) -> int:
    provider = get_embedding_provider()
    if not provider.available():
        print("FATAL: embedding provider 不可用（需 ARK_API_KEY + ARK_EMBEDDING_MODEL）")
        return 1
    res = await _calibrate(provider, w, hit_t, inject_t)
    rows, near_score, poison_score = res["rows"], res["near_score"], res["poison_score"]
    print(f"seeded source cases | w={w} hit_t={hit_t} inject_t={inject_t}")
    print(f"\n{'id':<5}{'band':<12}{'score':>7}  q")
    for r in rows:
        print(f"{r['id']:<5}{r['band']:<12}{r['score']:>7}  {r['question']}")
    syn_scores = [r["score"] for r in rows]
    syns = sorted(syn_scores)
    print(f"\n同义集 N={len(syns)} | min={syns[0]:.3f} p50={syns[len(syns)//2]:.3f} max={syns[-1]:.3f}")
    print(f"近重复: {near_score:.3f}（应 ≥ hit_t）| 毒化: {poison_score:.3f}（应 < hit_t，且 metrics 双保险）")
    frac_inject = sum(1 for sc in syn_scores if sc >= inject_t) / len(syn_scores)
    gate = near_score >= hit_t and frac_inject >= 0.60
    print(f"同义 ≥ inject_t({inject_t}): {frac_inject:.0%}（应 ≥60%）")
    print(f"\n硬门槛判定式: {'✅ PASS（近重复≥hit_t 且 ≥60% 同义≥inject_t）' if gate else '❌ FAIL → 回 design 改方案'}")
    return 0 if gate else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="混合检索阈值标定（真实方舟 API）")
    parser.add_argument("--w", type=float, default=0.7, help="融合权重（默认 0.7）")
    parser.add_argument("--hit-t", type=float, default=0.92, help="hit 阈值（默认 0.92，实测标定）")
    parser.add_argument("--inject-t", type=float, default=0.82, help="inject 阈值（默认 0.82，实测标定）")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.w, args.hit_t, args.inject_t)))


if __name__ == "__main__":
    main()
