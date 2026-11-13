"""MultiServerMCPClient setup and per-agent tool allowlists.

Agents never call GigSim, Upwork, a database or a file directly: every capability is an MCP tool. Each agent gets
only the tools listed for it in config (`mcp.allowlists`). Calls have a timeout and bounded retries with backoff;
when a server stays unreachable the call raises `ServerUnavailable`, which the graph turns into a queued job and the
UI shows as degraded mode.
"""
from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from common.config import load_config
from common.security import mint_service_token
from common.tracing import span, trace_headers

TOOL_SERVER = {
    "search_evidence": "portfolio", "get_case_study": "portfolio", "list_skills": "portfolio",
    "search_jobs": "marketplace", "get_job": "marketplace", "get_client_history": "marketplace",
    "get_connects_balance": "marketplace", "list_threads": "marketplace", "list_messages": "marketplace",
    "list_events": "marketplace", "list_proposals": "marketplace", "get_policy": "marketplace",
    "get_market_pricing": "marketplace", "create_proposal_draft": "marketplace", "submit_proposal": "marketplace",
    "send_message": "marketplace", "get_free_slots": "workspace", "create_interview_hold": "workspace",
    "create_email_draft": "workspace",
}


class ToolNotAllowed(PermissionError):
    pass


class ServerUnavailable(RuntimeError):
    def __init__(self, server: str, detail: str):
        super().__init__(f"{server} MCP server unavailable: {detail}")
        self.server = server


class ToolError(RuntimeError):
    def __init__(self, tool: str, error: str, detail: Any, retryable: bool):
        super().__init__(f"{tool}: {error} ({detail})")
        self.error, self.detail, self.retryable = error, detail, retryable


def server_urls() -> dict[str, str]:
    urls = dict(load_config()["mcp"]["servers"])
    for name in urls:
        urls[name] = os.environ.get(f"{name.upper()}_MCP_URL", urls[name])
    return urls


def allowed_tools(agent: str) -> list[str]:
    allowlists = load_config()["mcp"]["allowlists"]
    if agent not in allowlists:
        raise ToolNotAllowed(f"agent '{agent}' has no tool allowlist")
    return list(allowlists[agent])


class AgentTools:
    """Tool access for one agent on behalf of one user."""

    def __init__(self, agent: str, user_id: str, persona: str):
        self.agent = agent
        self.allowed = set(allowed_tools(agent))
        self.user_id = user_id
        self.persona = persona

    def _client(self, server: str) -> MultiServerMCPClient:
        scopes = ["portfolio", "marketplace", "workspace"]
        headers = {"Authorization": f"Bearer {mint_service_token(self.user_id, self.persona, scopes, 600)}",
                   **trace_headers()}
        timeout = load_config()["mcp"]["timeout_seconds"]
        return MultiServerMCPClient({server: {"transport": "streamable_http", "url": server_urls()[server],
                                              "headers": headers, "timeout": timedelta(seconds=timeout)}})

    def _open(self, server: str):
        """An MCP client session to `server` (tests replace this with an in-memory session)."""
        return self._client(server).session(server)

    async def call(self, tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call one allowed tool and return its structured result (`data` for marketplace tools)."""
        if tool not in self.allowed:
            raise ToolNotAllowed(f"agent '{self.agent}' may not call '{tool}'")
        server = TOOL_SERVER[tool]
        arguments = arguments or {}
        retries = load_config()["mcp"]["retries"]
        with span(f"tool.{tool}", kind="TOOL", agent=self.agent, tool=tool):
            last = ""
            for attempt in range(retries):
                try:
                    async with self._open(server) as session:
                        result = await session.call_tool(tool, arguments)
                except Exception as error:  # connection refused, timeout, protocol error
                    last = f"{type(error).__name__}: {error}"
                    await asyncio.sleep(min(6.0, 0.5 * 2 ** attempt))
                    continue
                if result.isError:
                    text = " ".join(getattr(c, "text", "") for c in result.content)
                    raise ToolError(tool, "tool_error", text[:500], retryable=False)
                data = result.structuredContent or {}
                if "result" in data and len(data) == 1:  # FastMCP wraps non-object results
                    data = data["result"]
                if isinstance(data, dict) and "ok" in data and "data" in data:  # marketplace ToolResult
                    if not data["ok"]:
                        if data.get("error") == "marketplace_unavailable":
                            raise ServerUnavailable("marketplace", str(data.get("detail")))
                        raise ToolError(tool, data.get("error", "error"), data.get("detail"),
                                        bool(data.get("retryable")))
                    return data["data"]
                return data
            raise ServerUnavailable(server, last)

    async def langchain_tools(self) -> list[Any]:
        """The agent's allowed tools as LangChain tools (for tool-calling agents and baselines)."""
        tools = []
        for server in sorted({TOOL_SERVER[t] for t in self.allowed}):
            client = self._client(server)
            tools += [t for t in await client.get_tools(server_name=server) if t.name in self.allowed]
        return tools


async def server_health() -> dict[str, bool]:
    """Which MCP servers answer right now (used by the degraded-mode banner)."""
    import httpx

    status = {}
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in server_urls().items():
            try:
                response = await client.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
                                             headers={"Accept": "application/json, text/event-stream"})
                status[name] = response.status_code < 500
            except httpx.HTTPError:
                status[name] = False
    return status
