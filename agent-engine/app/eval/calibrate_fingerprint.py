"""指纹阈值标定（metric-alias 任务 2.2）：MetricIdFingerprint.candidate_ids 的阈值。

相似度定义（P2-2 写死）：embedding cosine（方舟 provider），difflib 仅作降级。
判据（design D3）：毒化对全部落于阈值下 + 同义集期望映射全部落于阈值上。

用法（需 ARK_API_KEY + 已开通模型）：
    cd agent-engine && .venv/bin/python -m app.eval.calibrate_fingerprint
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.eval.runner import DEFAULT_CASES, load_cases
from app.memory.embeddings import get_embedding_provider
from app.memory.metric_ids import MetricIdFingerprint
from app.memory.retriever import normalize_question

ROOT = Path(__file__).resolve().parents[3]
_SYNONYM = Path(__file__).parent / "synonym_cases.yaml"


async def _calibrate(provider, threshold: float) -> dict:
    _date, golden = load_cases(DEFAULT_CASES)
    source_by_id = {c["id"]: c for c in golden if c.get("golden_spec")}
    syn_data = json.loads(_SYNONYM.read_text(encoding="utf-8"))["cases"]

    # 指纹表达集：catalog + 8 个 source cases 的沉淀表达（模拟写路径沉淀）
    catalog = json.loads((ROOT / "src" / "main" / "resources" / "metric_catalog.json").read_text())
    seen: set[str] = set()
    entries = []
    for s in syn_data:
        src = source_by_id[s["source_case"]]
        if src["id"] in seen:
            continue
        seen.add(src["id"])
        g = src["golden_spec"]
        entries.append(type("E", (), {
            "norm_question": normalize_question(src["question"]),
            "metric_codes": list(g.get("metrics") or []),
        })())

    fp = MetricIdFingerprint(catalog, entries=entries, provider=provider, threshold=threshold)

    rows = []
    for s in syn_data:
        ids = await fp.candidate_ids(s["question"])
        expect = set((s.get("golden_spec") or {}).get("metrics") or [])
        rows.append({"id": s["id"], "question": s["question"], "candidates": ids,
                     "expected": sorted(expect), "hit": bool(set(ids) & expect)})
    # 毒化对照：点赞量问题 vs 播放量表达集 → 不应命中 total_plays
    poison_ids = await fp.candidate_ids("最近7天点赞量是多少")
    return {
        "threshold": threshold,
        "rows": rows,
        "syn_total": len(rows),
        "syn_hit": sum(1 for r in rows if r["hit"]),
        "poison_ids": poison_ids,
        "poison_ok": "total_plays" not in poison_ids,
    }


async def main() -> None:
    provider = get_embedding_provider()
    if not provider.available():
        raise SystemExit("ARK_API_KEY 未配置，无法标定（需真实方舟 embedding）")
    for t in (0.5, 0.6, 0.7):
        r = await _calibrate(provider, threshold=t)
        print(f"threshold={t} syn_hit={r['syn_hit']}/{r['syn_total']} poison_ids={r['poison_ids']} poison_ok={r['poison_ok']}")
    print("建议：取 同义命中率最高 且 毒化全拦 的最小阈值（判据：毒化全落于阈值下 + 同义期望映射全落于阈值上）")


if __name__ == "__main__":
    asyncio.run(main())
