"""Schema snapshot: fails when any MCP tool's name, input schema, output schema or annotations change.

After an intended change, refresh the snapshot with:  UPDATE_SNAPSHOTS=1 pytest tests/contract
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.shared.memory import create_connected_server_and_client_session

from tests.harness import load_servers

SNAPSHOT = Path(__file__).parent / "snapshots" / "mcp_tools.json"


async def current_schemas() -> dict:
    out = {}
    for name, server in sorted(load_servers().items()):
        async with create_connected_server_and_client_session(server._mcp_server) as session:
            tools = (await session.list_tools()).tools
        out[name] = {t.name: {"input": t.inputSchema, "output": t.outputSchema,
                              "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None}
                     for t in sorted(tools, key=lambda t: t.name)}
    return out


async def test_tool_schemas_match_snapshot():
    schemas = await current_schemas()
    if os.environ.get("UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(schemas, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert schemas == expected, "MCP tool signatures changed; if intended, run UPDATE_SNAPSHOTS=1 pytest tests/contract"


async def test_every_agent_allowlist_names_real_tools():
    from agent.mcp_client import TOOL_SERVER
    from common.config import load_config

    schemas = await current_schemas()
    real = {tool for tools in schemas.values() for tool in tools}
    assert set(TOOL_SERVER) <= real
    for agent, tools in load_config()["mcp"]["allowlists"].items():
        assert set(tools) <= real, agent
