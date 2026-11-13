"""GigSim adapter: REST calls with timeouts, bounded retries with backoff, and honest error mapping.

429 and 5xx are retried (respecting Retry-After); after the last attempt the adapter raises MarketplaceUnavailable so
the graph can queue the work and the UI can show the degraded-mode banner.
"""
from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from common.tracing import trace_headers
from mcp_servers.marketplace.adapters.base import MarketplaceRejected, MarketplaceUnavailable

RETRIES = 4


class GigSimAdapter:
    name = "gigsim"

    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def _call(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None,
                    idempotency_key: str | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.token}", **trace_headers()}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        params = {k: v for k, v in (params or {}).items() if v not in (None, "", [])}
        last = ""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            for attempt in range(RETRIES):
                try:
                    response = await client.request(method, path, params=params, json=json, headers=headers)
                except httpx.HTTPError as error:
                    last = f"{type(error).__name__}: {error}"
                    await asyncio.sleep(min(8.0, 0.5 * 2 ** attempt) + random.random() * 0.2)
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    last = f"HTTP {response.status_code}"
                    retry_after = float(response.headers.get("Retry-After", 0) or 0)
                    await asyncio.sleep(max(retry_after, min(8.0, 0.5 * 2 ** attempt)) + random.random() * 0.2)
                    continue
                if response.status_code >= 400:
                    try:
                        detail = response.json()
                    except ValueError:
                        detail = response.text
                    raise MarketplaceRejected(response.status_code, detail)
                return response.json()
        raise MarketplaceUnavailable(f"GigSim unreachable after {RETRIES} attempts ({last})")

    async def search_jobs(self, query, skills, category, since, limit):
        return await self._call("GET", "/v1/jobs", params={"q": query, "skills": ",".join(skills),
                                                           "category": category, "since": since, "limit": limit})

    async def get_job(self, job_id):
        return await self._call("GET", f"/v1/jobs/{job_id}")

    async def get_client_history(self, client_id):
        return await self._call("GET", f"/v1/clients/{client_id}")

    async def get_connects_balance(self):
        return await self._call("GET", "/v1/connects")

    async def list_threads(self):
        return await self._call("GET", "/v1/threads")

    async def list_messages(self, thread_id):
        return await self._call("GET", f"/v1/threads/{thread_id}/messages")

    async def list_events(self, since):
        return await self._call("GET", "/v1/events", params={"since": since})

    async def list_proposals(self):
        return await self._call("GET", "/v1/proposals")

    async def get_policy(self):
        return await self._call("GET", "/v1/policy")

    async def get_market_pricing(self, category, skills):
        return await self._call("GET", "/v1/market/pricing", params={"category": category,
                                                                     "skills": ",".join(skills)})

    async def create_proposal_draft(self, body, idempotency_key, dry_run):
        return await self._call("POST", "/v1/proposals", params={"dry_run": str(dry_run).lower()}, json=body,
                                idempotency_key=idempotency_key)

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        return await self._call("POST", f"/v1/proposals/{proposal_id}/submit",
                                params={"dry_run": str(dry_run).lower()}, json={}, idempotency_key=idempotency_key)

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        return await self._call("POST", f"/v1/threads/{thread_id}/messages",
                                params={"dry_run": str(dry_run).lower()}, json={"text": text},
                                idempotency_key=idempotency_key)
