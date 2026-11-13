"""In-memory MCP harness: real MCP servers, real MCP client sessions, no network.

`InMemoryAgentTools` keeps the per-agent allowlists and result handling of `AgentTools` but opens sessions with
`create_connected_server_and_client_session`. The marketplace server's adapter is replaced by `FakeMarketplace`,
which behaves like GigSim (drafts, Connects, idempotency, events).
"""
from __future__ import annotations

import itertools

from agent.inmemory import InMemoryAgentTools, load_servers, tools_factory  # noqa: F401  (re-exported for tests)

class FakeMarketplace:
    name = "fake"

    def __init__(self, jobs: dict[str, dict] | None = None, down: bool = False):
        self.jobs = jobs or {}
        self.down = down
        self.proposals: dict[str, dict] = {}
        self.submits: list[str] = []
        self.sent: list[dict] = []
        self.balance = 100
        self._ids = itertools.count(1)
        self.threads = {"t1": [{"message_id": "m1", "thread_id": "t1", "sender": "client",
                                "text": "Could we do a quick call on Thursday?"}]}

    def _check(self):
        if self.down:
            from mcp_servers.marketplace.adapters.base import MarketplaceUnavailable

            raise MarketplaceUnavailable("GigSim unreachable (test)")

    async def search_jobs(self, query, skills, category, since, limit):
        self._check()
        return {"jobs": list(self.jobs.values())[:limit], "total": len(self.jobs)}

    async def get_job(self, job_id):
        self._check()
        return self.jobs[job_id]

    async def get_client_history(self, client_id):
        return {"client_id": client_id, "payment_verified": True, "total_spent": 12000, "hires": 9, "rating": 4.8}

    async def get_connects_balance(self):
        return {"balance": self.balance, "weekly_budget_left": 60}

    async def list_threads(self):
        return {"threads": [{"thread_id": t, "unread": 1} for t in self.threads]}

    async def list_messages(self, thread_id):
        return {"messages": self.threads[thread_id]}

    async def list_events(self, since):
        return {"events": []}

    async def list_proposals(self):
        return {"proposals": list(self.proposals.values())}

    async def get_policy(self):
        return {"version": "v1", "rules": []}

    async def get_market_pricing(self, category, skills):
        return {"category": category, "n": 40, "fixed": {"p25": 400, "p50": 700, "p75": 1100},
                "hourly": {"p25": 25, "p50": 40, "p75": 60}}

    async def create_proposal_draft(self, body, idempotency_key, dry_run):
        self._check()
        if dry_run:
            return {"dry_run": True, "would_create": body, "connects_cost": 8}
        proposal_id = f"prop-{next(self._ids)}"
        self.proposals[proposal_id] = {**body, "proposal_id": proposal_id, "status": "draft"}
        return {"proposal_id": proposal_id, "status": "draft"}

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        self._check()
        if dry_run:
            return {"dry_run": True, "connects_cost": 8}
        self.submits.append(proposal_id)
        self.balance -= 8
        return {"proposal_id": proposal_id, "status": "submitted", "connects_spent": 8}

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True}
        self.sent.append({"thread_id": thread_id, "text": text})
        return {"message_id": f"m{len(self.sent) + 10}", "status": "sent"}

