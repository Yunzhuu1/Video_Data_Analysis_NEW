"""标定脚本可复现单测（2.2）：mock provider 下同输入同输出。"""
import pytest

from app.eval import calibrate_thresholds as ct
from app.memory.embeddings import reset_embedding_provider
from tests.test_hybrid_retriever import CharBagProvider


@pytest.mark.asyncio
async def test_calibration_reproducible():
    reset_embedding_provider(CharBagProvider())
    try:
        r1 = await ct._calibrate(CharBagProvider(), 0.7, 0.92, 0.82)
        r2 = await ct._calibrate(CharBagProvider(), 0.7, 0.92, 0.82)
        assert r1["rows"] == r2["rows"]  # 同输入同输出（可复现）
        assert r1["near_score"] == r2["near_score"]
        assert r1["poison_score"] == r2["poison_score"]
        assert len(r1["rows"]) == 20
    finally:
        reset_embedding_provider(None)
