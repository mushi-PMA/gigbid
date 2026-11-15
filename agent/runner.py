"""Runs and resumes graph threads, publishes node-by-node progress, and records metrics.

Used by the worker (scheduled and queued runs) and by the API for approvals. Progress events go to the run bus
(Redis pub/sub, or in-process without Redis) so the UI can stream them; the last events are kept for page refresh.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from langgraph.types import Command

from agent.graphs.bid_graph import compile_bid_graph
from agent.graphs.conversation_graph import compile_conversation_graph
from agent.handoffs import Job
from agent.memory.store import get_checkpointer, get_store
from common.tracing import current_trace_id, span

KEEP_EVENTS = 200


# ---------------------------------------------------------------------------------------------------------
# Run bus
# ---------------------------------------------------------------------------------------------------------


class RunBus:
    def __init__(self) -> None:
        self._redis = None
        if os.environ.get("REDIS_URL"):
            import redis.asyncio as redis

            self._redis = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    async def publish(self, thread_id: str, event: dict[str, Any]) -> None:
        event = {"at": datetime.now(UTC).isoformat(), **event}
        if self._redis is not None:
            data = json.dumps(event, default=str)
            await self._redis.rpush(f"run:{thread_id}:events", data)
            await self._redis.ltrim(f"run:{thread_id}:events", -KEEP_EVENTS, -1)
            await self._redis.expire(f"run:{thread_id}:events", 7 * 24 * 3600)
            await self._redis.publish(f"run:{thread_id}", data)
            return
        self._history[thread_id] = (self._history[thread_id] + [event])[-KEEP_EVENTS:]
        for queue in self._queues[thread_id]:
            queue.put_nowait(event)

    async def history(self, thread_id: str) -> list[dict]:
        if self._redis is not None:
            return [json.loads(x) for x in await self._redis.lrange(f"run:{thread_id}:events", 0, -1)]
        return list(self._history[thread_id])

    async def subscribe(self, thread_id: str) -> AsyncIterator[dict]:
        if self._redis is not None:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(f"run:{thread_id}")
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        yield json.loads(message["data"])
            finally:
                await pubsub.unsubscribe(f"run:{thread_id}")
            return
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[thread_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._queues[thread_id].remove(queue)


bus = RunBus()

# ---------------------------------------------------------------------------------------------------------
# Graph access
# ---------------------------------------------------------------------------------------------------------

_graphs: dict[str, Any] = {}
_lock = asyncio.Lock()


async def graph(kind: str):
    async with _lock:
        if kind not in _graphs:
            checkpointer = await get_checkpointer()
            store = get_store()
            _graphs[kind] = (compile_bid_graph if kind == "bid" else compile_conversation_graph)(
                checkpointer=checkpointer, store=store)
    return _graphs[kind]


def bid_thread_id(user_id: str, job_id: str) -> str:
    return f"bid:{user_id}:{job_id}"


def conversation_thread_id(user_id: str, marketplace_thread: str) -> str:
    return f"conv:{user_id}:{marketplace_thread}"


def _config(thread_id: str, user_id: str, persona: str, settings: dict | None, extra: dict | None = None) -> dict:
    return {"configurable": {"thread_id": thread_id, "user_id": user_id, "persona": persona,
                             "settings": settings or {}, **(extra or {})},
            "recursion_limit": 80}


def _summary(state: dict[str, Any]) -> dict[str, Any]:
    """Small, UI-ready digest of a bid thread (stored in jobs_seen.summary for the inbox)."""
    out: dict[str, Any] = {"status": state.get("status"), "status_reason": state.get("status_reason", "")}
    if state.get("fit"):
        out["fit"] = round(state["fit"].score, 3)
    if state.get("risk"):
        risk = state["risk"]
        out["risk"] = round(risk.score, 3)
        out["risk_flags"] = sorted({f.kind for f in risk.flags})
        out["client_quality"] = risk.client_quality
    if state.get("decision"):
        out["action"] = state["decision"].action
    if state.get("price"):
        out["price"] = state["price"].amount
        out["payment_type"] = state["price"].payment_type
        out["connects_cost"] = state["price"].connects_cost
    out["tokens"] = state.get("tokens", 0)
    out["usd"] = round(state.get("usd", 0.0), 6)
    return out


async def _drive(kind: str, thread_id: str, payload: Any, config: dict, user_id: str,
                 job_id: str | None) -> dict[str, Any]:
    compiled = await graph(kind)
    started = time.perf_counter()
    run_id = uuid.uuid4().hex[:12]
    with span(f"run.{kind}", kind="CHAIN", thread_id=thread_id, user_id=user_id) as current:
        trace_id = current_trace_id()
        await bus.publish(thread_id, {"type": "run_started", "run_id": run_id, "trace_id": trace_id})
        async for chunk in compiled.astream(payload, config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if node_name == "__interrupt__":
                    await bus.publish(thread_id, {"type": "awaiting_approval", "run_id": run_id})
                    continue
                trace = (update or {}).get("trace", [{}])
                await bus.publish(thread_id, {"type": "node", "node": node_name, "run_id": run_id,
                                              "status": (update or {}).get("status"),
                                              "seconds": trace[-1].get("seconds") if trace else None,
                                              "tokens": trace[-1].get("tokens") if trace else None})
        snapshot = await compiled.aget_state(config)
        state = snapshot.values
        seconds = round(time.perf_counter() - started, 3)
        current.set_attribute("gigbid.status", str(state.get("status")))
    await bus.publish(thread_id, {"type": "run_finished", "run_id": run_id, "status": state.get("status"),
                                  "seconds": seconds})
    _record(run_id, user_id, kind, job_id, seconds, state, trace_id, thread_id)
    return {"thread_id": thread_id, "state": state, "pending": bool(snapshot.next), "trace_id": trace_id,
            "seconds": seconds}


def _record(run_id: str, user_id: str, kind: str, job_id: str | None, seconds: float, state: dict, trace_id: str,
            thread_id: str) -> None:
    if not os.environ.get("DATABASE_URL"):
        return
    from common import db

    by_node: dict[str, Any] = {}
    for entry in state.get("trace", []):
        row = by_node.setdefault(entry["node"], {"seconds": 0.0, "tokens": 0, "usd": 0.0, "runs": 0})
        row["seconds"] += entry.get("seconds", 0) or 0
        row["tokens"] += entry.get("tokens", 0) or 0
        row["usd"] += entry.get("usd", 0) or 0
        row["runs"] += 1
    db.execute("INSERT INTO run_metrics VALUES (%s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s)",
               (run_id, user_id, kind, job_id, seconds, int(state.get("tokens", 0)), float(state.get("usd", 0.0)),
                str(state.get("status")), trace_id, json.dumps(by_node)))
    if kind == "conversation":
        db.execute("INSERT INTO conversations (user_id, marketplace_thread, graph_thread_id, job_id, status) VALUES "
                   "(%s, %s, %s, %s, %s) ON CONFLICT (user_id, marketplace_thread) DO UPDATE SET status = "
                   "EXCLUDED.status, updated_at = now()",
                   (user_id, state.get("thread_id", ""), thread_id, state.get("job_id", ""), str(state.get("status"))))
    if kind == "bid" and job_id:
        # merge, never replace: the scout's title, budget and full job must survive (re-analysis needs the job)
        db.execute("UPDATE jobs_seen SET status = %s, summary = summary || %s::jsonb, thread_id = %s, "
                   "updated_at = now() WHERE user_id = %s AND job_id = %s",
                   (str(state.get("status")), json.dumps(_summary(state), default=str), thread_id, user_id, job_id))


# ---------------------------------------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------------------------------------


LOCKED_STATUSES = ("awaiting_approval", "approved", "submitted")


async def fresh_thread(compiled, config: dict) -> bool:
    """A new analysis of a job starts from a clean thread: the old run's step, token and revision counters and its
    critiques would otherwise add to the new run and trip its budgets. A thread whose draft waits for the human, or
    was approved or sent, is never wiped (a new draft would carry a new idempotency key and could be sent twice):
    returns False and the caller leaves it alone."""
    snapshot = await compiled.aget_state(config)
    if snapshot.next or snapshot.values.get("status") in LOCKED_STATUSES:
        return False
    if snapshot.values:
        await compiled.checkpointer.adelete_thread(config["configurable"]["thread_id"])
    return True


async def run_bid(user_id: str, persona: str, job: Job, settings: dict | None = None,
                  duplicate_of: str | None = None) -> dict[str, Any]:
    thread_id = bid_thread_id(user_id, job.job_id)
    config = _config(thread_id, user_id, persona, settings, {"duplicate_of": duplicate_of})
    compiled = await graph("bid")
    if not await fresh_thread(compiled, config):    # a draft waits for approval or was sent: nothing to redo
        snapshot = await compiled.aget_state(config)
        return {"thread_id": thread_id, "state": snapshot.values, "pending": bool(snapshot.next), "trace_id": "",
                "seconds": 0.0}
    inputs = {"user_id": user_id, "persona": persona, "job": job, "status": "running"}
    return await _drive("bid", thread_id, inputs, config, user_id, job.job_id)


async def run_conversation(user_id: str, persona: str, marketplace_thread: str, job_id: str = "",
                           settings: dict | None = None) -> dict[str, Any]:
    thread_id = conversation_thread_id(user_id, marketplace_thread)
    config = _config(thread_id, user_id, persona, settings)
    inputs = {"user_id": user_id, "persona": persona, "thread_id": marketplace_thread, "job_id": job_id,
              "status": "running"}
    return await _drive("conversation", thread_id, inputs, config, user_id, None)


async def resume(thread_id: str, user_id: str, persona: str, decision: dict[str, Any],
                 settings: dict | None = None) -> dict[str, Any]:
    kind = "bid" if thread_id.startswith("bid:") else "conversation"
    config = _config(thread_id, user_id, persona, settings)
    job_id = thread_id.split(":", 2)[2] if kind == "bid" else None
    return await _drive(kind, thread_id, Command(resume=decision), config, user_id, job_id)


async def get_thread(thread_id: str, user_id: str, persona: str) -> dict[str, Any]:
    kind = "bid" if thread_id.startswith("bid:") else "conversation"
    compiled = await graph(kind)
    snapshot = await compiled.aget_state(_config(thread_id, user_id, persona, None))
    interrupts = [i.value for task in snapshot.tasks for i in (task.interrupts or [])]
    return {"values": snapshot.values, "next": list(snapshot.next), "pending_approval": interrupts[0]
            if interrupts else None, "created_at": snapshot.created_at}


async def history(thread_id: str, user_id: str, persona: str) -> list[dict[str, Any]]:
    """Checkpoint history: every step of the thread, newest first (for replay from any node)."""
    kind = "bid" if thread_id.startswith("bid:") else "conversation"
    compiled = await graph(kind)
    rows = []
    async for snapshot in compiled.aget_state_history(_config(thread_id, user_id, persona, None)):
        rows.append({"checkpoint_id": snapshot.config["configurable"]["checkpoint_id"], "next": list(snapshot.next),
                     "status": snapshot.values.get("status"), "step": snapshot.metadata.get("step"),
                     "created_at": snapshot.created_at})
    return rows


async def replay(thread_id: str, checkpoint_id: str, user_id: str, persona: str,
                 settings: dict | None = None) -> dict[str, Any]:
    """Re-run a thread from any earlier checkpoint (a new branch of its history)."""
    kind = "bid" if thread_id.startswith("bid:") else "conversation"
    config = _config(thread_id, user_id, persona, settings, {"checkpoint_id": checkpoint_id})
    job_id = thread_id.split(":", 2)[2] if kind == "bid" else None
    return await _drive(kind, thread_id, None, config, user_id, job_id)
