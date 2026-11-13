"""Portfolio MCP server through an in-memory MCP client: tools, resource templates and prompts."""
from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session


async def test_search_get_and_list(fixture_personas, monkeypatch, tmp_path):
    from mcp_servers.portfolio import server

    monkeypatch.setenv("PORTFOLIO_PERSONA", "test_dev")
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as session:
        found = (await session.call_tool("search_evidence", {"requirement": "nightly Airflow loads", "k": 3}))
        items = found.structuredContent["items"]
        assert items and items[0]["project"] == "p1" and {"type", "source", "date", "outcome"} <= set(items[0])

        only_won = await session.call_tool("search_evidence", {"requirement": "proposal", "k": 5,
                                                                "filters": {"types": ["proposal"],
                                                                            "outcome": ["won"]}})
        assert all(i["outcome"] == "won" for i in only_won.structuredContent["items"])

        case = await session.call_tool("get_case_study", {"case_id": "cs-1"})
        assert "Airflow" in case.structuredContent["body"]

        skills = await session.call_tool("list_skills", {})
        assert any(s["skill"] == "Airflow" for s in skills.structuredContent["skills"])

        templates = {t.uriTemplate for t in (await session.list_resource_templates()).resourceTemplates}
        assert {"portfolio://case/{case_id}", "portfolio://proposal/{proposal_id}"} <= templates
        resource = await session.read_resource("portfolio://proposal/prop-1")
        assert "won" in resource.contents[0].text

        prompts = {p.name for p in (await session.list_prompts()).prompts}
        assert "answer_screening_question" in prompts
