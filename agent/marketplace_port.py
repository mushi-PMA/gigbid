"""The single marketplace interface the graph uses.

Every call goes through the Marketplace MCP server, which routes it to the GigSim or the live Upwork adapter
(`mcp_servers/marketplace/adapters/`) according to `marketplace.mode` in config. The graph therefore cannot tell
which marketplace it is talking to. Results come back as typed hand-off objects.
"""
from __future__ import annotations

from typing import Any

from agent.handoffs import ClientHistory, ConnectsBalance, Job, Message
from agent.mcp_client import AgentTools


def _job(raw: dict[str, Any]) -> Job:
    return Job.model_validate({k: v for k, v in raw.items() if k in Job.model_fields})


class MarketplacePort:
    def __init__(self, tools: AgentTools):
        self.tools = tools

    async def search_jobs(self, query: str = "", skills: list[str] | None = None, category: str = "",
                          since: str | None = None, limit: int = 30) -> list[Job]:
        data = await self.tools.call("search_jobs", {"query": query, "skills": skills or [], "category": category,
                                                     "since": since, "limit": limit})
        return [_job(j) for j in data.get("jobs", [])]

    async def get_job(self, job_id: str) -> Job:
        return _job(await self.tools.call("get_job", {"job_id": job_id}))

    async def get_client_history(self, client_id: str) -> ClientHistory:
        raw = await self.tools.call("get_client_history", {"client_id": client_id})
        return ClientHistory.model_validate({k: v for k, v in raw.items() if k in ClientHistory.model_fields})

    async def get_connects_balance(self) -> ConnectsBalance:
        return ConnectsBalance.model_validate(await self.tools.call("get_connects_balance"))

    async def list_threads(self) -> list[dict[str, Any]]:
        return (await self.tools.call("list_threads")).get("threads", [])

    async def list_messages(self, thread_id: str) -> list[Message]:
        data = await self.tools.call("list_messages", {"thread_id": thread_id})
        return [Message.model_validate({k: v for k, v in m.items() if k in Message.model_fields})
                for m in data.get("messages", [])]

    async def list_events(self, since: str | None = None) -> list[dict[str, Any]]:
        return (await self.tools.call("list_events", {"since": since})).get("events", [])

    async def list_proposals(self) -> list[dict[str, Any]]:
        return (await self.tools.call("list_proposals")).get("proposals", [])

    async def get_policy(self) -> dict[str, Any]:
        return await self.tools.call("get_policy")

    async def get_market_pricing(self, category: str, skills: list[str]) -> dict[str, Any]:
        return await self.tools.call("get_market_pricing", {"category": category, "skills": skills[:10]})

    async def create_proposal_draft(self, payload: dict[str, Any], idempotency_key: str, *, dry_run: bool,
                                    approval_token: str | None = None) -> dict[str, Any]:
        return await self.tools.call("create_proposal_draft", {**payload, "idempotency_key": idempotency_key,
                                                               "dry_run": dry_run, "approval_token": approval_token})

    async def submit_proposal(self, proposal_id: str, job_id: str, approved_payload: dict[str, Any],
                              idempotency_key: str, *, dry_run: bool, approval_token: str | None = None) \
            -> dict[str, Any]:
        return await self.tools.call("submit_proposal", {
            "proposal_id": proposal_id, "job_id": job_id, "approved_payload": approved_payload,
            "idempotency_key": idempotency_key, "dry_run": dry_run, "approval_token": approval_token})

    async def send_message(self, thread_id: str, text: str, idempotency_key: str, *, dry_run: bool,
                           approval_token: str | None = None) -> dict[str, Any]:
        return await self.tools.call("send_message", {"thread_id": thread_id, "text": text,
                                                      "idempotency_key": idempotency_key, "dry_run": dry_run,
                                                      "approval_token": approval_token})
