"""MemoryStore：agent-engine 本地 SQLite（aiosqlite）沉淀成功语义路径。

设计约束（semantic-memory change）：
- 只存 ResolvedIntent（含确定性兜底后值），不存 SQL——记忆永远不直接进 SQL。
- 写钩子只负责新条目沉淀（sql_source=semantic）；命中 run 走 record_hit 独立路径。
- 失效：metric_codes catalog 校验（口径变更删除）+ resolver_hash 内容哈希（规则变更降级）。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS semantic_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_question TEXT NOT NULL,
    resolved_intent TEXT NOT NULL,
    metric_codes TEXT NOT NULL,
    hit_count INTEGER NOT NULL DEFAULT 1,
    last_hit_at TEXT NOT NULL,
    resolver_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_norm ON semantic_memory(norm_question);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def compute_resolver_hash() -> str:
    """语义规则版本：prompt 与 resolver 文件内容哈希（规则变更自动失效，防忘 bump）。"""
    h = hashlib.sha256()
    base = Path(__file__).resolve().parents[1]
    for rel in ("prompts/semantic.py", "agents/semantic_resolver.py"):
        h.update((base / rel).read_bytes())
    return h.hexdigest()[:16]


@dataclass
class MemoryEntry:
    norm_question: str
    resolved_intent: dict[str, Any]
    metric_codes: list[str]
    resolver_hash: str
    hit_count: int = 1
    id: int | None = None
    last_hit_at: str = field(default_factory=_now)

    @classmethod
    def from_row(cls, row: tuple) -> MemoryEntry:
        return cls(
            id=row[0],
            norm_question=row[1],
            resolved_intent=json.loads(row[2]),
            metric_codes=json.loads(row[3]),
            hit_count=row[4],
            last_hit_at=row[5],
            resolver_hash=row[6],
        )


class MemoryStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def upsert(self, norm_question: str, resolved_intent: dict[str, Any],
                     metric_codes: list[str], resolver_hash: str) -> int:
        """新条目沉淀；同 norm_question 已存在则更新 hit_count/last_hit_at，返回 entry_id。"""
        conn = self._conn
        if conn is None:
            raise RuntimeError("MemoryStore not initialized")
        now = _now()
        cursor = await conn.execute(
            "SELECT id, hit_count FROM semantic_memory WHERE norm_question = ?", (norm_question,))
        row = await cursor.fetchone()
        if row is None:
            cur = await conn.execute(
                "INSERT INTO semantic_memory (norm_question, resolved_intent, metric_codes,"
                " hit_count, last_hit_at, resolver_hash, created_at) VALUES (?,?,?,1,?,?,?)",
                (norm_question, json.dumps(resolved_intent, ensure_ascii=False),
                 json.dumps(metric_codes), now, resolver_hash, now))
            entry_id = cur.lastrowid
        else:
            entry_id = row[0]
            await conn.execute(
                "UPDATE semantic_memory SET hit_count = hit_count + 1, last_hit_at = ? WHERE id = ?",
                (now, entry_id))
        await conn.commit()
        return entry_id

    async def record_hit(self, entry_id: int) -> None:
        """命中 run 独立路径：仅更新 hit_count/last_hit_at（不经过写钩子）。"""
        if self._conn is None:
            raise RuntimeError("MemoryStore not initialized")
        await self._conn.execute(
            "UPDATE semantic_memory SET hit_count = hit_count + 1, last_hit_at = ? WHERE id = ?",
            (_now(), entry_id))
        await self._conn.commit()

    async def find_by_question(self, norm_question: str) -> MemoryEntry | None:
        if self._conn is None:
            raise RuntimeError("MemoryStore not initialized")
        cursor = await self._conn.execute(
            "SELECT * FROM semantic_memory WHERE norm_question = ?", (norm_question,))
        row = await cursor.fetchone()
        return MemoryEntry.from_row(row) if row else None

    async def all(self) -> list[MemoryEntry]:
        if self._conn is None:
            raise RuntimeError("MemoryStore not initialized")
        cursor = await self._conn.execute("SELECT * FROM semantic_memory")
        return [MemoryEntry.from_row(r) for r in await cursor.fetchall()]

    async def delete(self, entry_id: int) -> None:
        if self._conn is None:
            raise RuntimeError("MemoryStore not initialized")
        await self._conn.execute("DELETE FROM semantic_memory WHERE id = ?", (entry_id,))
        await self._conn.commit()

    async def clear(self) -> None:
        if self._conn is not None:
            await self._conn.execute("DELETE FROM semantic_memory")
            await self._conn.commit()
