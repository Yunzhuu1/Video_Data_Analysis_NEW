import pytest
import pytest_asyncio

from app.api import routes
from app.graph import graph_builder, nodes
from app.settings import settings


class _FakeProvider:
    def __init__(self, available: bool):
        self._available = available

    def available(self) -> bool:
        return self._available


class _FakeStore:
    def __init__(self):
        self.close_calls = 0

    async def close(self):
        self.close_calls += 1


@pytest_asyncio.fixture(autouse=True)
async def clean_runtime():
    await graph_builder.close_memory()
    settings.memory_enabled = True
    yield
    await graph_builder.close_memory()


def test_resolve_memory_path_is_backend_specific(monkeypatch):
    monkeypatch.setattr(settings, "memory_db_path", "chosen.sqlite")
    monkeypatch.setattr(settings, "memory_lance_path", "chosen.lance")

    assert graph_builder.resolve_memory_path("sqlite") == "chosen.sqlite"
    assert graph_builder.resolve_memory_path("lance") == "chosen.lance"


@pytest.mark.asyncio
async def test_explicit_memory_path_isolated_and_old_store_closed(monkeypatch):
    old = _FakeStore()
    new = _FakeStore()
    nodes.memory = old

    async def fake_build(path, **kwargs):
        assert path == ":memory:"
        assert kwargs["backend"] == "sqlite"
        return new

    monkeypatch.setattr("app.memory.vector_store.build_memory_store", fake_build)
    await graph_builder.init_memory(":memory:")

    assert nodes.memory is new
    assert old.close_calls == 1
    assert graph_builder.memory_runtime_status()["status"] == "READY"
    assert graph_builder.memory_runtime_status()["backend"] == "sqlite"


@pytest.mark.asyncio
async def test_lance_embedding_unavailable_is_degraded(monkeypatch, tmp_path):
    monkeypatch.setattr("app.memory.embeddings.get_embedding_provider",
                        lambda: _FakeProvider(False))

    await graph_builder.init_memory(str(tmp_path / "memory.lance"), backend="lance")

    assert nodes.memory is None
    assert graph_builder.memory_runtime_status() == {
        "enabled": True,
        "backend": "lance",
        "status": "DEGRADED",
        "reason_code": "EMBEDDING_UNAVAILABLE",
    }


@pytest.mark.asyncio
async def test_invalid_sqlite_directory_is_degraded_and_health_exposes_reason(tmp_path):
    await graph_builder.init_memory(str(tmp_path), backend="sqlite")

    response = await routes.health()
    assert response.status == "UP"
    assert response.memory.status == "DEGRADED"
    assert response.memory.reason_code == "INVALID_STORE_PATH"
    assert nodes.memory is None


@pytest.mark.asyncio
async def test_store_init_failure_does_not_destroy_ready_old_store(monkeypatch):
    old = _FakeStore()
    nodes.memory = old

    async def fail_build(*args, **kwargs):
        raise RuntimeError("secret/raw failure")

    monkeypatch.setattr("app.memory.vector_store.build_memory_store", fail_build)
    await graph_builder.init_memory(":memory:", backend="sqlite")

    assert nodes.memory is old
    assert old.close_calls == 0


@pytest.mark.asyncio
async def test_close_memory_is_idempotent():
    store = _FakeStore()
    nodes.memory = store

    await graph_builder.close_memory()
    await graph_builder.close_memory()

    assert store.close_calls == 1
    assert nodes.memory is None
    assert graph_builder.memory_runtime_status()["status"] == "DISABLED"
