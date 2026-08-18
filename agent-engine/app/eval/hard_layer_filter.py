"""难层筛选脚本（eval-data-expansion 2.2/3.2）。

对同义集 hard 层候选：
1. 组 A（--memory off）真实跑 → L1 判定
2. 沉淀 source cases → 运行时 band（复用 _compute_synonym_bands，与线上同一检索器）
3. 输出三列判定表：组A L1 / band / 判定（真难层 / miss泛化层 / 非难层）

判定（P1 双重条件）：真难层 = 组A L1<100% 且 band=inject；
band=miss 的难层条目 → miss 泛化层（LLM 自身泛化，注入不可达，单独报告）。
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.eval.comparator import compare_spec
from app.eval.runner import (
    DEFAULT_CASES,
    _close_memory,
    _compute_synonym_bands,
    _experiment_memory_path,
    load_cases,
    run_chatbi_graph,
)
from app.graph import graph_builder
from app.memory.embeddings import get_embedding_provider
from app.settings import settings

_SYNONYM = Path(__file__).parent / "synonym_cases.yaml"


def classify(a_l1: bool, band: str) -> str:
    """判定：真难层 = 组A错 且 band=inject；组A错且 band=miss → miss泛化层；组A对 → 非难层。"""
    if not a_l1 and band == "inject":
        return "真难层"
    if not a_l1:
        return "miss泛化层"
    return "非难层(组A对)"


async def run() -> dict:
    from langgraph.checkpoint.memory import InMemorySaver

    provider = get_embedding_provider()
    if not provider.available():
        raise RuntimeError("embedding provider 不可用（需 ARK_API_KEY + ARK_EMBEDDING_MODEL）")

    syn_data = json.loads(_SYNONYM.read_text(encoding="utf-8"))["cases"]
    hard = [s for s in syn_data if s.get("difficulty") == "hard"]
    _d, golden = load_cases(DEFAULT_CASES)
    source_by_id = {c["id"]: c for c in golden if c.get("golden_spec")}
    eval_date = _d

    graph_builder.init_graph(InMemorySaver())
    rows: list[dict] = []

    # 组 A：memory off（纯 LLM 基线）
    settings.memory_enabled = False
    for s in hard:
        state = await run_chatbi_graph({
            "run_id": f"hardA_{s['id']}", "user_id": "eval", "question": s["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
        score = compare_spec(state.get("resolved_intent"), s.get("golden_spec"), eval_date)
        rows.append({"id": s["id"], "question": s["question"], "source": s.get("source_case"),
                     "a_l1": bool(score and score.core_ok)})

    # 沉淀 source + 运行时 band（与线上同一检索器）
    settings.memory_enabled = True
    from app.graph.graph_builder import init_memory
    await init_memory(_experiment_memory_path())
    for s in hard:
        src = source_by_id.get(s.get("source_case"))
        if src is None:
            continue
        await run_chatbi_graph({
            "run_id": f"hardSeed_{src['id']}", "user_id": "eval", "question": src["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
    bands = await _compute_synonym_bands([s["question"] for s in hard], settings.memory_namespace)
    for r in rows:
        r["band"] = bands[r["question"]]
        r["verdict"] = classify(r["a_l1"], r["band"])

    # 组 B：只跑 真难层 子集（band=inject 且 组A错）——注入实验统计口径（P1）
    true_hard = [r for r in rows if r["verdict"] == "真难层"]
    for r in true_hard:
        state = await run_chatbi_graph({
            "run_id": f"hardB_{r['id']}", "user_id": "eval", "question": r["question"],
            "graph_mode": "chatbi", "memory_namespace": settings.memory_namespace,
            "warnings": [], "errors": []})
        score = compare_spec(state.get("resolved_intent"),
                             next(s["golden_spec"] for s in hard if s["id"] == r["id"]), eval_date)
        r["b_l1"] = bool(score and score.core_ok)
        r["b_intent"] = state.get("resolved_intent")
    await _close_memory()

    # 汇总
    counts = {"真难层": 0, "miss泛化层": 0, "非难层(组A对)": 0}
    for r in rows:
        counts[r["verdict"]] += 1
    flips = [r for r in true_hard if r.get("b_l1") and not r["a_l1"]]
    return {"hard_n": len(rows), "counts": counts, "true_hard_n": len(true_hard),
            "flip_n": len(flips), "rows": rows}


async def main() -> int:
    print(f"{'id':<6}{'band':<10}{'判定':<14} 组A L1  q")
    try:
        res = await run()
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}")
        return 1
    print(f"{'id':<6}{'band':<10}{'判定':<14}{'组A':<6}{'组B':<6} q")
    for r in res["rows"]:
        b = "—" if "b_l1" not in r else str(r.get("b_l1"))
        print(f"{r['id']:<6}{r['band']:<10}{r['verdict']:<14}{r['a_l1']!s:<6}{b:<6} {r['question']}")
    print(f"\nhard 候选 N={res['hard_n']} | {res['counts']}")
    print(f"真难层 = {res['true_hard_n']}（≥8 才有注入实验统计意义，否则并入诚实报告）")
    if res["true_hard_n"]:
        gain = res["flip_n"] / res["true_hard_n"]
        print(f"注入实验（真难层子集）：组B 翻转 {res['flip_n']}/{res['true_hard_n']} "
              f"= {gain:.0%}（最小声明口径：至少 1 例翻转，不宣称显著提升）")
        for r in [x for x in res["rows"] if x["verdict"] == "真难层"]:
            print(f"  flip: {r['question'][:24]} | 组A={'错' if not r['a_l1'] else '对'} "
                  f"组B={'对' if r.get('b_l1') else '错'} | band={r['band']}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="难层筛选（真实 LLM + embedding）")
    parser.parse_args()
    raise SystemExit(asyncio.run(main()))
