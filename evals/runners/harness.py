"""Evaluation harness: the real graph and the real MCP servers in one process, over an offline copy of GigSim.

`EvalMarketplace` serves dev and holdout jobs, the seeded client histories and the market pricing exactly as GigSim
does, and scores submitted proposals with GigSim's simulated clients (hidden preferences, plus the client model when
GIGSIM_LLM=on). The human approval step is simulated by approving the draft unchanged, which is only done here, to
measure outcomes; the product never sends without a human.
"""

from __future__ import annotations

import itertools
import json
import os
import time
from typing import Any

from langgraph.store.memory import InMemoryStore
from langgraph.types import Command

from agent.graphs.bid_graph import compile_bid_graph
from agent.handoffs import Job
from agent.inmemory import tools_factory
from agent.memory.store import memory_saver
from common.config import ROOT
from common.llm import start_usage
from common.security import mint_approval_token, payload_hash

SEED = ROOT / "data" / "gigsim"


class EvalMarketplace:
    name = "eval"

    def __init__(self, jobs: list[dict[str, Any]]):
        self.jobs = {j["job_id"]: {k: v for k, v in j.items() if k not in ("kind", "source", "history")} for j in jobs}
        self.raw = {j["job_id"]: j for j in jobs}
        self.clients = {c["client_id"]: c for c in json.loads((SEED / "clients.json").read_text(encoding="utf-8"))}
        self.pricing = json.loads((SEED / "pricing.json").read_text(encoding="utf-8"))
        self.proposals: dict[str, dict] = {}
        self.outcomes: dict[str, dict] = {}
        self._ids = itertools.count(1)

    async def search_jobs(self, query, skills, category, since, limit):
        return {"jobs": list(self.jobs.values())[:limit], "total": len(self.jobs)}

    async def get_job(self, job_id):
        return self.jobs[job_id]

    async def get_client_history(self, client_id):
        client = self.clients.get(client_id)
        if client is None:
            from mcp_servers.marketplace.adapters.base import MarketplaceRejected

            raise MarketplaceRejected(404, "unknown client")
        return client["public"]

    async def get_connects_balance(self):
        return {"balance": 120, "weekly_budget_left": 120}

    async def list_threads(self):
        return {"threads": []}

    async def list_messages(self, thread_id):
        return {"messages": []}

    async def list_events(self, since):
        return {"events": []}

    async def list_proposals(self):
        return {"proposals": list(self.proposals.values())}

    async def get_policy(self):
        from common.config import load_policy

        return load_policy()

    async def get_market_pricing(self, category, skills):
        by_skill = {name.lower(): s for name, s in self.pricing.get("skills", {}).items()}
        categories = {name.lower(): s for name, s in self.pricing.get("categories", {}).items()}
        candidates = [by_skill[s.lower()] for s in skills if s.lower() in by_skill]
        chosen = (
            max(candidates, key=lambda s: s["n"])
            if candidates
            else categories.get((category or "").lower())
            or self.pricing.get("all")
            or {"n": 0, "fixed": {}, "hourly": {}}
        )
        band = lambda s: {k: s.get(k) for k in ("p25", "p50", "p75")}  # noqa: E731
        return {
            "category": category,
            "n": chosen["n"],
            "fixed": band(chosen["fixed"]),
            "hourly": band(chosen["hourly"]),
        }

    async def create_proposal_draft(self, body, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True, "would_create": body}
        proposal_id = f"eval-prop-{next(self._ids)}"
        self.proposals[proposal_id] = {**body, "proposal_id": proposal_id}
        return {"proposal_id": proposal_id, "status": "draft"}

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True}
        from gigsim import clients as sim

        proposal = self.proposals[proposal_id]
        job = self.raw[proposal["job_id"]]
        client = self.clients.get(job.get("client_id"), {"hidden": {}})
        decision = sim.decide(client["hidden"], job, proposal, job.get("kind", "regular"))
        if os.environ.get("GIGSIM_LLM", "off") == "on":
            verdict = sim.llm_decision(client["hidden"], job, proposal, decision.score)
            if verdict is not None:
                decision = sim.apply_verdict(decision, verdict)
        self.outcomes[proposal["job_id"]] = {
            "score": decision.score,
            "viewed": decision.viewed,
            "replied": decision.replied,
            "interview": decision.interview,
            "hired": decision.hired,
            "used_llm": decision.used_llm,
        }
        return {"proposal_id": proposal_id, "status": "submitted", "connects_spent": job.get("connects_cost", 0)}

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        return {"dry_run": dry_run}


def install(market: EvalMarketplace, persona: str) -> None:
    from agent.inmemory import load_servers
    from mcp_servers.marketplace import server

    load_servers()
    server._adapter = lambda user_id, p: market
    server._idempotency.clear()
    os.environ["PORTFOLIO_PERSONA"] = persona
    os.environ["MCP_DEFAULT_PERSONA"] = persona


async def run_job(job: dict[str, Any], persona: str, *, approve: bool = False, graph=None) -> dict[str, Any]:
    """Run one job through the bid graph; optionally approve the draft unchanged (simulated human)."""
    graph = graph or compile_bid_graph(memory_saver(), InMemoryStore())
    thread = f"eval:{persona}:{job['job_id']}"
    config = {
        "configurable": {
            "thread_id": thread,
            "user_id": "local",
            "persona": persona,
            "tools_factory": tools_factory,
            "settings": {},
        },
        "recursion_limit": 80,
    }
    usage = start_usage()
    started = time.perf_counter()
    inputs = {
        "user_id": "local",
        "persona": persona,
        "status": "running",
        "job": Job.model_validate({k: v for k, v in job.items() if k in Job.model_fields}),
    }
    await graph.ainvoke(inputs, config)
    analysed_seconds = time.perf_counter() - started
    snapshot = await graph.aget_state(config)
    state = snapshot.values
    drafted = bool(snapshot.next)
    if approve and drafted:
        request = snapshot.tasks[0].interrupts[0].value
        payload = request["payload"]
        decision = {
            "action": "approve",
            "payload_hash": payload_hash(payload),
            "approval_token": mint_approval_token("local", "submit_proposal", payload["job_id"], payload),
        }
        state = await graph.ainvoke(Command(resume=decision), config)
    return {
        "state": state,
        "drafted": drafted,
        "seconds": time.perf_counter() - started,
        "analysed_seconds": analysed_seconds,
        # each node meters its own calls into the state (the trace entries), so totals come from there
        "tokens": int(state.get("tokens") or usage.total_tokens),
        "usd": float(state.get("usd") or usage.usd),
        "by_node": {e["node"]: e.get("by_model", {}) for e in state.get("trace", [])},
    }
