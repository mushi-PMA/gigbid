"""Run the agents against the real MCP servers in the same process (no network): used by tests and evaluation.

`InMemoryAgentTools` keeps the per-agent allowlists and result handling of `AgentTools` and opens MCP sessions with
`create_connected_server_and_client_session`.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from mcp.shared.memory import create_connected_server_and_client_session

from agent.mcp_client import AgentTools

SERVERS: dict[str, Any] = {}


def load_servers() -> dict[str, Any]:
    if not SERVERS:
        os.environ.setdefault("MCP_AUTH", "off")
        from mcp_servers.marketplace import server as marketplace
        from mcp_servers.portfolio import server as portfolio
        from mcp_servers.workspace import server as workspace

        SERVERS.update(portfolio=portfolio.mcp, marketplace=marketplace.mcp, workspace=workspace.mcp)
    return SERVERS


class InMemoryAgentTools(AgentTools):
    @asynccontextmanager
    async def _open(self, server: str):
        async with create_connected_server_and_client_session(load_servers()[server]._mcp_server) as session:
            yield session


def tools_factory(agent: str, user_id: str, persona: str) -> AgentTools:
    return InMemoryAgentTools(agent, user_id, persona)
