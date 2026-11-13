"""Long-term memory store (LangGraph store) and the Postgres checkpointer.

Postgres (`DATABASE_URL`) backs both in deployment; tests and offline evaluation use the in-memory versions.
"""
from __future__ import annotations

import os
from functools import lru_cache

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore


@lru_cache(maxsize=1)
def get_store() -> BaseStore:
    url = os.environ.get("DATABASE_URL")
    if not url or os.environ.get("MEMORY_STORE") == "memory":
        return InMemoryStore()
    from langgraph.store.postgres import PostgresStore
    from psycopg import Connection
    from psycopg.rows import dict_row

    conn = Connection.connect(url.replace("+psycopg", ""), autocommit=True, prepare_threshold=0,
                              row_factory=dict_row)
    store = PostgresStore(conn)
    store.setup()
    return store


async def get_checkpointer():
    """Async Postgres checkpointer (durable threads); in-memory saver without a database."""
    url = os.environ.get("DATABASE_URL")
    if not url or os.environ.get("CHECKPOINTER") == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    conn = await AsyncConnection.connect(url.replace("+psycopg", ""), autocommit=True, prepare_threshold=0,
                                         row_factory=dict_row)
    saver = AsyncPostgresSaver(conn)
    await saver.setup()
    return saver
