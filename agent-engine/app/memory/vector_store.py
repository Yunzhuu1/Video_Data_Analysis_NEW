"""LanceVectorStore：LanceDB 嵌入式列式向量库实现的记忆存储（路径 B 的存储侧）。

- 与 MemoryStore（SQLite）同接口（upsert/find/all/clear/delete/record_hit）+ 向量/FTS 检索。
- 写入时同步 embed（provider 注入）；embedding 失败 → 不持久化（返回 -1，记忆为增强不打断主链路）。
- 向量 search 与 FTS search 分开查，融合由 HybridRetriever 按 D4 公式自算（不消费引擎融合分）。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import pyarrow as pa

from app.memory.store import MemoryEntry, _now

logger = logging.getLogger(__name__)

DEFAULT_VECTOR_DIM = 2048  # doubao-embedding-vision 实测维度


def _make_schema(vector_dim: int) -> pa.Schema:
    return pa.schema([
        pa.field("id", pa.int64()),
        pa.field("namespace", pa.string()),
        pa.field("norm_question", pa.string()),
        pa.field("resolved_intent", pa.string()),
        pa.field("metric_codes", pa.list_(pa.string())),
        pa.field("hit_count", pa.int64()),
        pa.field("last_hit_at", pa.string()),
        pa.field("resolver_hash", pa.string()),
        pa.field("embedding_model", pa.string()),
        pa.field("created_at", pa.string()),
        pa.field("embedding", pa.list_(pa.float32(), vector_dim)),
    ])


def _esc(value: str) -> str:
    """where 子句字符串转义（值来自 normalize_question/namespace，防注入）。"""
    return value.replace("'", "''")


class LanceVectorStore:
    """LanceDB 记忆库：单表 = MemoryEntry 字段 + embedding 向量。"""

    def __init__(self, path: str, provider=None, embedding_model: str = "",
                 vector_dim: int = DEFAULT_VECTOR_DIM) -> None:
        self.path = path
        self.provider = provider  # EmbeddingProvider | None（upsert 需要；None 则跳过 embedding）
        self.embedding_model = embedding_model
        self.vector_dim = vector_dim
        self._db = None
        self._table = None
        self._indexed = False

    # ------------------------------------------------------------------ 生命周期
    async def init(self) -> None:
        import lancedb

        self._db = lancedb.connect(self.path)
        tables = self._db.list_tables()
        if hasattr(tables, "tables"):  # lancedb>=0.37: list_tables() 返回 ListTablesResponse 对象
            tables = tables.tables
        if "memory" not in tables:
            self._table = self._db.create_table("memory", schema=_make_schema(self.vector_dim))
        else:
            self._table = self._db.open_table("memory")
        # 索引须在非空表上创建（空表会报 Not supported）；首批数据写入后惰性建
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        """有数据后建 HNSW(cosine) 向量索引 + ICU 中文 FTS 索引（已建则忽略；索引随写入自动更新）。"""
        if self._table is None or self._indexed:
            return
        if self._table.count_rows() == 0:
            return
        from lancedb.index import FTS, HnswFlat
        try:
            self._table.create_index("embedding", config=HnswFlat(distance_type="cosine"))
        except Exception as exc:  # noqa: BLE001 - 已存在等
            logger.debug("vector index create skipped: %s", exc)
        try:
            self._table.create_index("norm_question", config=FTS(base_tokenizer="icu"))
        except Exception as exc:  # noqa: BLE001
            logger.debug("fts index create skipped: %s", exc)
        self._indexed = True

    async def close(self) -> None:
        self._db = None
        self._table = None

    # ------------------------------------------------------------------ 写入
    async def upsert(self, norm_question: str, resolved_intent: dict[str, Any],
                     metric_codes: list[str], resolver_hash: str,
                     namespace: str = "default") -> int:
        """新条目沉淀；同 (namespace, norm_question) 已存在则更新。embedding 失败返回 -1（不持久化）。"""
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        vec: list[float] = []
        if self.provider is not None:
            vec = await self.provider.embed(norm_question)
        if not vec:
            logger.warning("embedding failed/empty, skip persist: %s", norm_question)
            return -1
        now = _now()
        existing = await self.find_by_question(norm_question, namespace)
        if existing is None:
            new_id = self._next_id()
            row = pa.table({
                "id": [new_id], "namespace": [namespace], "norm_question": [norm_question],
                "resolved_intent": [json.dumps(resolved_intent, ensure_ascii=False)],
                "metric_codes": [list(metric_codes)], "hit_count": [1],
                "last_hit_at": [now], "resolver_hash": [resolver_hash],
                "embedding_model": [self.embedding_model], "created_at": [now],
                "embedding": [list(vec)],
            })
            self._table.add(row)
            await self._ensure_indexes()
            return new_id
        self._table.update(where=f"id = {existing.id}", values={
            "resolved_intent": json.dumps(resolved_intent, ensure_ascii=False),
            "metric_codes": list(metric_codes),
            "hit_count": int(existing.hit_count) + 1,
            "last_hit_at": now,
            "resolver_hash": resolver_hash,
            "embedding": list(vec),
            "embedding_model": self.embedding_model,
        })
        return existing.id

    async def record_hit(self, entry_id: int) -> None:
        """命中 run 独立路径：仅更新 hit_count/last_hit_at。"""
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        arrow = self._table.to_arrow()
        idx = [i for i, v in enumerate(arrow["id"].to_pylist()) if v == entry_id]
        if not idx:
            return
        hc = int(arrow["hit_count"][idx[0]].as_py())
        self._table.update(where=f"id = {entry_id}",
                           values={"hit_count": hc + 1, "last_hit_at": _now()})

    # ------------------------------------------------------------------ 读取
    async def find_by_question(self, norm_question: str, namespace: str = "default") -> MemoryEntry | None:
        for e in await self.all(namespace):
            if e.norm_question == norm_question:
                return e
        return None

    async def all(self, namespace: str | None = None) -> list[MemoryEntry]:
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        rows = self._table.to_arrow().to_pylist()
        out = []
        for r in rows:
            if namespace is not None and r["namespace"] != namespace:
                continue
            out.append(self._to_entry(r))
        return out

    async def search_by_vector(self, embedding: list[float], namespace: str,
                               limit: int = 10) -> list[tuple[MemoryEntry, float]]:
        """LanceDB 向量 search（HNSW cosine）。返回 [(entry, cosine_sim)]，cos_sim = 1 - _distance。"""
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        results = (
            self._table.search(list(embedding))
            .where(f"namespace = '{_esc(namespace)}'", prefilter=True)
            .limit(limit).to_list()
        )
        out = []
        for r in results:
            dist = r.get("_distance")
            if dist is None:
                continue
            out.append((self._to_entry(r), max(0.0, 1.0 - float(dist))))
        return out

    async def fts_search(self, query: str, namespace: str,
                         limit: int = 10) -> list[tuple[MemoryEntry, float]]:
        """LanceDB FTS（BM25, ICU 中文分词）。返回 [(entry, bm25_score)]。"""
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        results = (
            self._table.search(query, query_type="fts")
            .where(f"namespace = '{_esc(namespace)}'", prefilter=True)
            .limit(limit).to_list()
        )
        out = []
        for r in results:
            score = r.get("_score")
            if not score:
                continue
            out.append((self._to_entry(r), float(score)))
        return out

    # ------------------------------------------------------------------ 管理
    async def clear(self, namespace: str | None = None) -> None:
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        if namespace is None:
            self._table.delete("id >= 0")
        else:
            self._table.delete(f"namespace = '{_esc(namespace)}'")

    async def delete(self, entry_id: int) -> None:
        if self._table is None:
            raise RuntimeError("LanceVectorStore not initialized")
        self._table.delete(f"id = {entry_id}")

    # ------------------------------------------------------------------ 内部
    def _next_id(self) -> int:
        arrow = self._table.to_arrow()
        ids = arrow["id"].to_pylist()
        return (max(ids) + 1) if ids else 1

    def _to_entry(self, r: dict[str, Any]) -> MemoryEntry:
        try:
            intent = json.loads(r.get("resolved_intent") or "{}")
        except json.JSONDecodeError:  # pragma: no cover
            intent = {}
        return MemoryEntry(
            id=int(r["id"]),
            namespace=r["namespace"],
            norm_question=r["norm_question"],
            resolved_intent=intent,
            metric_codes=list(r.get("metric_codes") or []),
            hit_count=int(r.get("hit_count") or 1),
            last_hit_at=r.get("last_hit_at") or "",
            resolver_hash=r.get("resolver_hash") or "",
        )


async def build_memory_store(db_path: str, backend: str | None = None,
                             provider=None, embedding_model: str = "") -> Any:
    """记忆存储工厂：backend='lance' → LanceVectorStore；否则 SQLite MemoryStore。"""
    from app.memory.store import MemoryStore

    backend = (backend or "sqlite").lower()
    if backend == "lance":
        store = LanceVectorStore(db_path, provider=provider, embedding_model=embedding_model)
        await store.init()
        return store
    store = MemoryStore(db_path)
    await store.init()
    return store
