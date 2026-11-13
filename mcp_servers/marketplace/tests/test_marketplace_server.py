"""Marketplace MCP server through an in-memory MCP client: schemas, approval gate, dry run, idempotency, errors."""
from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from common.payloads import draft_payload
from common.security import mint_approval_token
from tests.harness import FakeMarketplace


@pytest.fixture
def market(monkeypatch, tmp_path):
    from mcp_servers.marketplace import server

    fake = FakeMarketplace({"j1": {"job_id": "j1", "title": "Airflow job", "description": "d"}})
    monkeypatch.setattr(server, "_adapter", lambda user_id, persona: fake)
    monkeypatch.setattr(server, "_idempotency", {})
    monkeypatch.setenv("IDEMPOTENCY_STORE", str(tmp_path / "idem.json"))
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    return server, fake


async def call(server, tool, args):
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        result = await session.call_tool(tool, args)
        return result.structuredContent


LETTER = "Your nightly loads fail and nobody notices until morning. I built a fix for exactly this before."


async def test_write_without_approval_is_refused(market):
    server, fake = market
    out = await call(server, "create_proposal_draft", {"job_id": "j1", "cover_letter": LETTER, "bid_amount": 500,
                                                       "payment_type": "fixed", "idempotency_key": "key-00001"})
    assert out["ok"] is False and out["error"] == "approval_required" and not fake.proposals


async def test_dry_run_changes_nothing(market):
    server, fake = market
    out = await call(server, "create_proposal_draft", {"job_id": "j1", "cover_letter": LETTER, "bid_amount": 500,
                                                       "payment_type": "fixed", "idempotency_key": "key-00002",
                                                       "dry_run": True})
    assert out["ok"] and out["data"]["dry_run"] and not fake.proposals


async def test_retried_submit_spends_connects_once(market):
    server, fake = market
    payload = draft_payload("j1", LETTER, [], 500, "fixed")
    token = mint_approval_token("local", "submit_proposal", "j1", payload)
    draft = await call(server, "create_proposal_draft", {**payload, "idempotency_key": "draft-k1",
                                                         "approval_token": token})
    proposal_id = draft["data"]["proposal_id"]
    args = {"proposal_id": proposal_id, "job_id": "j1", "approved_payload": payload, "idempotency_key": "submit-k1",
            "approval_token": token}
    first = await call(server, "submit_proposal", args)
    second = await call(server, "submit_proposal", args)
    assert first["ok"] and second["ok"] and second["data"].get("idempotent_replay")
    assert fake.submits == [proposal_id] and fake.balance == 92


async def test_approval_for_other_content_is_refused(market):
    server, fake = market
    payload = draft_payload("j1", LETTER, [], 500, "fixed")
    token = mint_approval_token("local", "submit_proposal", "j1", payload)
    out = await call(server, "create_proposal_draft", {**payload, "bid_amount": 5000, "idempotency_key": "draft-k2",
                                                       "approval_token": token})
    assert out["error"] == "approval_required" and "changed" in out["detail"]


async def test_input_schema_constraints_are_enforced(market):
    server, _ = market
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        result = await session.call_tool("create_proposal_draft", {"job_id": "j1", "cover_letter": "short",
                                                                   "bid_amount": -5, "payment_type": "fixed",
                                                                   "idempotency_key": "k"})
    assert result.isError


async def test_unavailable_marketplace_is_reported_as_retryable(market):
    server, fake = market
    fake.down = True
    out = await call(server, "get_job", {"job_id": "j1"})
    assert out == {"ok": False, "data": {}, "error": "marketplace_unavailable",
                   "detail": "GigSim unreachable (test)", "retryable": True}


async def test_annotations_mark_reads_and_writes(market):
    server, _ = market
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        tools = {t.name: t for t in (await session.list_tools()).tools}
    assert tools["get_job"].annotations.readOnlyHint is True
    assert tools["submit_proposal"].annotations.destructiveHint is True
    assert tools["submit_proposal"].annotations.idempotentHint is True
    assert tools["create_proposal_draft"].outputSchema is not None
