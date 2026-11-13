"""Shared test fixtures. Every test runs offline: scripted model replies, in-memory MCP sessions, in-memory stores."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Callable

import pytest

os.environ.setdefault("VECTOR_STORE", "memory")
os.environ.setdefault("MEMORY_STORE", "memory")
os.environ.setdefault("CHECKPOINTER", "memory")
os.environ.setdefault("MCP_AUTH", "off")
os.environ.pop("DATABASE_URL", None)
os.environ.pop("REDIS_URL", None)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def scripted_llm() -> Callable[[dict[str, Any]], None]:
    """Install scripted replies: {node: reply or callable(system, user) -> reply or list of replies}."""
    from common import llm

    def install(replies: dict[str, Any]) -> None:
        counters: dict[str, int] = {}

        def handler(node: str, system: str, user: str) -> str:
            reply = replies.get(node)
            if reply is None:
                raise AssertionError(f"no scripted reply for node '{node}'")
            if callable(reply):
                reply = reply(system, user)
            if isinstance(reply, list):
                index = counters.get(node, 0)
                counters[node] = index + 1
                reply = reply[min(index, len(reply) - 1)]
            return reply if isinstance(reply, str) else json.dumps(reply)

        llm.set_scripted_responses(handler)

    yield install
    llm.set_scripted_responses(None)


@pytest.fixture
def fixture_personas(tmp_path, monkeypatch) -> Path:
    """A tiny persona corpus copied to a temp dir and indexed in memory."""
    from rag import retriever
    from rag.index import store
    from rag.ingest import loaders

    target = tmp_path / "personas"
    shutil.copytree(FIXTURES / "personas", target)
    monkeypatch.setattr(loaders, "PERSONAS_DIR", target)
    monkeypatch.setattr(store, "PROCESSED", tmp_path / "processed")
    retriever._index_cache.clear()
    return target
