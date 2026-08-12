"""Persistent checkpointing for human-in-the-loop approval resumes.

Replaces the old process-local in-memory store with LangGraph's SQLite
checkpointer (aiosqlite-backed), so a waiting approval can be resumed after a
process restart or from another instance sharing the same DB file.
"""
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


async def create_checkpointer(db_path: str) -> AsyncSqliteSaver:
    """Create a long-lived async SQLite checkpointer.

    ``db_path`` may be a file path or ``":memory:"`` for tests.
    """
    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver
