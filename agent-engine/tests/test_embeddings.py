import pytest

from app.memory.embeddings import EmbeddingProvider, get_embedding_provider, reset_embedding_provider
from app.settings import settings


def test_provider_available_requires_key_and_model():
    p = EmbeddingProvider(api_key="k", model="m")
    assert p.available() is True
    p2 = EmbeddingProvider(api_key="", model="m")
    assert p2.available() is False
    p3 = EmbeddingProvider(api_key="k", model="")
    assert p3.available() is False


def test_base_url_normalization():
    p = EmbeddingProvider(base_url="https://ark.cn-beijing.volces.com", api_key="k", model="m")
    p2 = EmbeddingProvider(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key="k", model="m")
    assert p.url == p2.url == "https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal"


@pytest.mark.asyncio
async def test_embed_failure_returns_none(monkeypatch):
    """真实调用失败 → None（降级 difflib，不打断主链路）。"""
    p = EmbeddingProvider(api_key="k", model="m")

    class _Resp:
        def raise_for_status(self):
            raise RuntimeError("network down")

    class _Client:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return _Resp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    assert await p.embed("测试") is None


@pytest.mark.asyncio
async def test_embed_no_key_returns_none():
    p = EmbeddingProvider(api_key="", model="m")
    assert await p.embed("测试") is None


@pytest.mark.asyncio
async def test_get_provider_singleton_and_reset():
    reset_embedding_provider()
    p1 = get_embedding_provider()
    p2 = get_embedding_provider()
    assert p1 is p2
    reset_embedding_provider()
    assert get_embedding_provider() is not p1
    reset_embedding_provider(None)
