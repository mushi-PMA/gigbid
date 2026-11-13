"""Workspace MCP server: free calendar slots, tentative interview holds and email drafts.

Backed by a local store (SQLite at WORKSPACE_DB) that behaves like a calendar and a mailbox: working hours, existing
busy blocks, holds that block later slots, and drafts that are never sent from here. The agent sees MCP tools only,
so swapping in Google Calendar and Gmail later changes this file and nothing else.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from common import audit
from common.config import ROOT
from common.security import ServiceTokenVerifier
from common.tracing import setup_tracing

SERVER = "workspace"
PORT = int(os.environ.get("WORKSPACE_MCP_PORT", "8103"))
PUBLIC_URL = os.environ.get("WORKSPACE_MCP_URL", f"http://localhost:{PORT}/mcp")
AUTH = os.environ.get("MCP_AUTH", "on") == "on"
WORK_START, WORK_END = time(9, 0), time(17, 0)

setup_tracing("mcp-workspace")
mcp = FastMCP(
    "gigbid-workspace", instructions="Calendar slots, tentative interview holds and email drafts for GigBid.",
    token_verifier=ServiceTokenVerifier() if AUTH else None,
    auth=AuthSettings(issuer_url=os.environ.get("API_PUBLIC_URL", "http://localhost:8000"),
                      resource_server_url=PUBLIC_URL, required_scopes=["workspace"]) if AUTH else None,
    host=os.environ.get("MCP_HOST", "127.0.0.1"), port=PORT, stateless_http=True, json_response=True)


def _db() -> sqlite3.Connection:
    path = Path(os.environ.get("WORKSPACE_DB", ROOT / "data" / "audit" / "workspace.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, user_id TEXT, start TEXT, end TEXT, "
                 "title TEXT, kind TEXT, thread_id TEXT, idem TEXT UNIQUE)")
    conn.execute("CREATE TABLE IF NOT EXISTS drafts (id TEXT PRIMARY KEY, user_id TEXT, recipient TEXT, subject TEXT, "
                 "body TEXT, created TEXT, idem TEXT UNIQUE)")
    return conn


def _user() -> str:
    token = get_access_token()
    return token.claims["sub"] if token is not None and token.claims else os.environ.get("MCP_DEFAULT_USER", "local")


class Slot(BaseModel):
    start: str
    end: str


class Slots(BaseModel):
    timezone: str
    slots: list[Slot]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                                      openWorldHint=False), title="Free calendar slots")
async def get_free_slots(
    from_date: Annotated[str, Field(description="YYYY-MM-DD, first day to search")],
    days: Annotated[int, Field(ge=1, le=14)] = 5,
    duration_minutes: Annotated[int, Field(ge=15, le=180)] = 30,
    tz: Annotated[str, Field(description="IANA time zone of the freelancer")] = "Asia/Karachi",
    max_slots: Annotated[int, Field(ge=1, le=10)] = 3,
) -> Slots:
    """Free slots in working hours (09:00 to 17:00, Monday to Friday), avoiding busy blocks and holds."""
    zone = ZoneInfo(tz)
    user = _user()
    with _db() as conn:
        busy = [(datetime.fromisoformat(s), datetime.fromisoformat(e))
                for s, e in conn.execute("SELECT start, end FROM events WHERE user_id = ?", (user,))]
    slots: list[Slot] = []
    day = datetime.fromisoformat(from_date).date()
    for _ in range(days):
        if day.weekday() < 5:
            cursor = datetime.combine(day, WORK_START, zone)
            end_of_day = datetime.combine(day, WORK_END, zone)
            while cursor + timedelta(minutes=duration_minutes) <= end_of_day and len(slots) < max_slots:
                end = cursor + timedelta(minutes=duration_minutes)
                if all(end <= b_start or cursor >= b_end for b_start, b_end in busy):
                    slots.append(Slot(start=cursor.isoformat(), end=end.isoformat()))
                    cursor = end + timedelta(minutes=90)  # spread the offers over the day
                else:
                    cursor += timedelta(minutes=30)
        day += timedelta(days=1)
    audit.write(user, SERVER, "get_free_slots", {"from_date": from_date, "days": days}, {"n": len(slots)}, True)
    return Slots(timezone=tz, slots=slots)


class Hold(BaseModel):
    hold_id: str
    start: str
    end: str
    title: str
    status: str = "tentative"


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                      openWorldHint=False), title="Create tentative interview hold")
async def create_interview_hold(
    start: Annotated[str, Field(description="ISO start time with offset")],
    duration_minutes: Annotated[int, Field(ge=15, le=180)],
    title: Annotated[str, Field(min_length=3, max_length=120)],
    thread_id: Annotated[str, Field(min_length=1, max_length=80)],
    idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
) -> Hold:
    """Block a tentative slot for an interview the client may accept (idempotent)."""
    user = _user()
    begin = datetime.fromisoformat(start)
    end = begin + timedelta(minutes=duration_minutes)
    with _db() as conn:
        row = conn.execute("SELECT id, start, end, title FROM events WHERE idem = ?", (idempotency_key,)).fetchone()
        if row is None:
            hold_id = f"hold-{uuid.uuid4().hex[:10]}"
            conn.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, 'hold', ?, ?)",
                         (hold_id, user, begin.isoformat(), end.isoformat(), title, thread_id, idempotency_key))
            row = (hold_id, begin.isoformat(), end.isoformat(), title)
    audit.write(user, SERVER, "create_interview_hold", {"start": start, "thread_id": thread_id}, {"id": row[0]}, True)
    return Hold(hold_id=row[0], start=row[1], end=row[2], title=row[3])


class EmailDraft(BaseModel):
    draft_id: str
    subject: str
    status: str = "draft (not sent)"


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True,
                                      openWorldHint=False), title="Create email draft")
async def create_email_draft(
    recipient_label: Annotated[str, Field(min_length=1, max_length=120, description="Name, not an address")],
    subject: Annotated[str, Field(min_length=1, max_length=200)],
    body: Annotated[str, Field(min_length=1, max_length=5000)],
    idempotency_key: Annotated[str, Field(min_length=8, max_length=120)],
) -> EmailDraft:
    """Save an email draft for the freelancer to review; nothing is sent."""
    user = _user()
    with _db() as conn:
        row = conn.execute("SELECT id, subject FROM drafts WHERE idem = ?", (idempotency_key,)).fetchone()
        if row is None:
            row = (f"draft-{uuid.uuid4().hex[:10]}", subject)
            conn.execute("INSERT INTO drafts VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (row[0], user, recipient_label, subject, body, datetime.now(timezone.utc).isoformat(),
                          idempotency_key))
    audit.write(user, SERVER, "create_email_draft", {"subject": subject}, {"id": row[0]}, True)
    return EmailDraft(draft_id=row[0], subject=row[1])


@mcp.resource("workspace://calendar", mime_type="application/json")
def calendar_resource() -> str:
    """Upcoming holds and busy blocks."""
    with _db() as conn:
        rows = conn.execute("SELECT id, start, end, title, kind FROM events WHERE user_id = ? ORDER BY start",
                            (_user(),)).fetchall()
    return json.dumps([dict(zip(["id", "start", "end", "title", "kind"], r)) for r in rows])


if __name__ == "__main__":
    import sys

    mcp.run(transport="stdio" if "--stdio" in sys.argv else "streamable-http")
