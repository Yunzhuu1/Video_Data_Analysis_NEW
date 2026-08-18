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
    await _close_memory()

    # 汇总
    counts = {"真难层": 0, "miss泛化层": 0, "非难层(组A对)": 0}
    for r in rows:
        counts[r["verdict"]] += 1
    return {"hard_n": len(rows), "counts": counts, "rows": rows}


async def main() -> int:
    print(f"{'id':<6}{'band':<10}{'判定':<14} 组A L1  q")
    try:
        res = await run()
    except Exception as exc:  # noqa: BLE001
        print(f"FATAL: {exc}")
        return 1
    for r in res["rows"]:
        print(f"{r['id']:<6}{r['band']:<10}{r['verdict']:<14}{r['a_l1']!s:<7} {r['question']}")
    print(f"\nhard 候选 N={res['hard_n']} | {res['counts']}")
    true_hard = res["counts"]["真难层"]
    print(f"真难层 = {true_hard}（≥8 才有注入实验统计意义，否则并入诚实报告）")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="难层筛选（真实 LLM + embedding）")
    parser.parse_args()
    raise SystemExit(asyncio.run(main()))
