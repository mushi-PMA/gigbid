"""Connect a live Upwork account through the official Upwork MCP server (OAuth 2.1, PKCE, dynamic registration).

`GET /connect` starts the flow and returns the Upwork authorization URL; Upwork redirects back to `/callback`, which
completes it. Tokens are stored encrypted per user (adapters/upwork_live.py) and are never logged.
"""
from __future__ import annotations

import asyncio
import os

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from apps.api.auth.users import CurrentUser
from common.config import load_config
from mcp_servers.marketplace.adapters.upwork_live import oauth_provider

router = APIRouter(prefix="/api/integrations/upwork", tags=["integrations"])
_pending: dict[str, dict] = {}   # state -> {"user_id", "url": Future, "code": Future}


def _redirect_uri() -> str:
    return os.environ.get("UPWORK_REDIRECT_URI", "http://localhost:8000/api/integrations/upwork/callback")


async def _run_flow(user_id: str, flow: dict) -> None:
    async def redirect_handler(url: str) -> None:
        flow["url"].set_result(url)

    async def callback_handler() -> tuple[str, str | None]:
        return await asyncio.wait_for(flow["code"], timeout=600)

    provider = oauth_provider(user_id, _redirect_uri(), redirect_handler, callback_handler)
    try:
        async with httpx.AsyncClient(auth=provider, timeout=30) as client:
            await client.post(load_config()["marketplace"]["upwork"]["mcp_url"],
                              json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                              headers={"Accept": "application/json, text/event-stream"})
    except Exception as error:  # surface the failure to the waiting /connect call
        if not flow["url"].done():
            flow["url"].set_exception(error)


@router.get("/connect")
async def connect(user: dict = CurrentUser) -> dict:
    loop = asyncio.get_running_loop()
    flow = {"user_id": user["user_id"], "url": loop.create_future(), "code": loop.create_future()}
    task = asyncio.create_task(_run_flow(user["user_id"], flow))
    try:
        url = await asyncio.wait_for(asyncio.shield(flow["url"]), timeout=30)
    except Exception as error:
        task.cancel()
        raise HTTPException(502, f"could not start the Upwork sign-in: {error}") from error
    state = httpx.URL(url).params.get("state", "")
    _pending[state] = flow
    return {"authorization_url": url}


@router.get("/callback", include_in_schema=False)
async def callback(code: str, state: str = "") -> RedirectResponse:
    flow = _pending.pop(state, None)
    if flow is None:
        raise HTTPException(400, "unknown or expired sign-in attempt")
    flow["code"].set_result((code, state))
    return RedirectResponse(os.environ.get("WEB_PUBLIC_URL", "http://localhost:5173") + "/settings?upwork=connected")
