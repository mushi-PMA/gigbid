"""Workspace MCP server through an in-memory MCP client: free slots skip holds; holds and drafts are idempotent."""
from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session


async def test_slots_holds_and_drafts(monkeypatch, tmp_path):
    from mcp_servers.workspace import server

    monkeypatch.setenv("WORKSPACE_DB", str(tmp_path / "ws.db"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        slots = (await session.call_tool("get_free_slots", {"from_date": "2026-11-16", "days": 2,
                                                            "tz": "UTC"})).structuredContent["slots"]
        assert slots and slots[0]["start"].startswith("2026-11-16T09:00")
        hold_args = {"start": slots[0]["start"], "duration_minutes": 30, "title": "Interview", "thread_id": "t1",
                     "idempotency_key": "hold-key-1"}
        first = (await session.call_tool("create_interview_hold", hold_args)).structuredContent
        again = (await session.call_tool("create_interview_hold", hold_args)).structuredContent
        assert first["hold_id"] == again["hold_id"]
        after = (await session.call_tool("get_free_slots", {"from_date": "2026-11-16", "days": 2,
                                                            "tz": "UTC"})).structuredContent["slots"]
        assert after[0]["start"] != slots[0]["start"]
        draft = await session.call_tool("create_email_draft", {"recipient_label": "Client", "subject": "Times",
                                                               "body": "Thursday 10:00", "idempotency_key": "mail-key-1"})
        assert draft.structuredContent["status"].startswith("draft")
