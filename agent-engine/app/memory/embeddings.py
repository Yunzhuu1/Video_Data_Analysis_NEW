"""EmbeddingProvider：火山方舟 doubao-embedding（多模态端点 + 文本输入）封装。

- 一次调用返回 1 个 embedding（input 列表 = 单文档多模态内容）→ 批量逐条调。
- 可注入/mock（CI 无 key 可跑）；失败 → 告警 + 返回 None（检索降级 difflib）。
- base URL 容错：允许带或不带 `/api/v3` 后缀。
"""
from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)

_provider: "EmbeddingProvider | None" = None


class EmbeddingProvider:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 30.0) -> None:
        base = (base_url or settings.ark_base_url).rstrip("/")
        base = re.sub(r"/api/v3$", "", base)
        self.url = f"{base}/api/v3/embeddings/multimodal"
        self.api_key = api_key if api_key is not None else settings.ark_api_key
        self.model = model if model is not None else settings.ark_embedding_model
        self.timeout = timeout

    def available(self) -> bool:
        """key + model 都配了才算可用（真实调用还可能因网络失败返回 None）。"""
        return bool(self.api_key and self.model)

    async def embed(self, text: str) -> list[float] | None:
        if not self.available():
            return None
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "input": [{"type": "text", "text": text}]},
                )
                resp.raise_for_status()
                data = resp.json().get("data")
                emb = data.get("embedding") if isinstance(data, dict) else data[0]["embedding"]
                return list(emb) if emb is not None else None
        except Exception as exc:  # noqa: BLE001 - 记忆失败不打断主链路
            logger.warning("embedding failed (%s): %s", self.model, exc)
            return None


def get_embedding_provider() -> "EmbeddingProvider | None":
    """模块级单例（懒创建）。测试可调用 reset_embedding_provider() 注入 mock。"""
    global _provider
    if _provider is None:
        _provider = EmbeddingProvider()
    return _provider


def reset_embedding_provider(provider: "EmbeddingProvider | None" = None) -> None:
    global _provider
    _provider = provider
