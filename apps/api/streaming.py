"""Server-Sent Events bridge from LangGraph run progress to the browser (node by node)."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from sse_starlette.sse import EventSourceResponse

from agent.runner import bus


async def _events(thread_id: str) -> AsyncIterator[dict]:
    for event in await bus.history(thread_id):  # replay what happened before the page opened (refresh-safe)
        yield {"event": event.get("type", "message"), "data": json.dumps(event, default=str)}
    stream = bus.subscribe(thread_id)
    while True:
        try:
            event = await asyncio.wait_for(stream.__anext__(), timeout=15)
        except TimeoutError:
            yield {"event": "ping", "data": "{}"}
            continue
        except StopAsyncIteration:
            return
        yield {"event": event.get("type", "message"), "data": json.dumps(event, default=str)}


def sse(thread_id: str) -> EventSourceResponse:
    return EventSourceResponse(_events(thread_id))
