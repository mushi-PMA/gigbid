"""Agent run viewer: live node-by-node stream (SSE), checkpoint history, replay from any node, trace link."""
from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from agent import runner
from apps.api.auth.users import CurrentUser, get_settings
from apps.api.schemas.models import RunInfo, TraceStep
from apps.api.streaming import sse

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _owned(thread_id: str, user_id: str) -> None:
    if thread_id.split(":")[1:2] != [user_id]:
        raise HTTPException(404, "not found")


def trace_url(trace_id: str | None) -> str | None:
    base = os.environ.get("PHOENIX_PUBLIC_URL")
    return f"{base.rstrip('/')}/redirects/traces/{trace_id}" if base and trace_id else None


@router.get("/{thread_id}/stream")
async def stream(thread_id: str, user: dict = CurrentUser):
    _owned(thread_id, user["user_id"])
    return sse(thread_id)


@router.get("/{thread_id}", response_model=RunInfo)
async def run_info(thread_id: str, user: dict = CurrentUser) -> RunInfo:
    _owned(thread_id, user["user_id"])
    events = await runner.bus.history(thread_id)
    trace_ids = [e.get("trace_id") for e in events if e.get("trace_id")]
    steps = await runner.history(thread_id, user["user_id"], user["persona"])
    return RunInfo(thread_id=thread_id, events=events, trace_url=trace_url(trace_ids[-1] if trace_ids else None),
                   history=[TraceStep(**{**s, "created_at": str(s["created_at"]) if s["created_at"] else None})
                            for s in steps])


@router.post("/{thread_id}/replay/{checkpoint_id}", status_code=202)
async def replay(thread_id: str, checkpoint_id: str, user: dict = CurrentUser) -> dict:
    """Re-run the thread from an earlier checkpoint (read-only nodes re-execute; submissions stay idempotent)."""
    _owned(thread_id, user["user_id"])
    result = await runner.replay(thread_id, checkpoint_id, user["user_id"], user["persona"],
                                 get_settings(user["user_id"]))
    return {"thread_id": thread_id, "status": result["state"].get("status"), "pending": result["pending"]}
