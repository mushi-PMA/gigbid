"""Part A deliverable: a single agent drafting one grounded proposal for a GigSim job, using only MCP tools.

The agent connects to the running Marketplace and Portfolio MCP servers over Streamable HTTP (MultiServerMCPClient),
reads one live GigSim job, searches the portfolio for evidence of each requirement, and writes a proposal whose every
experience claim cites an evidence id. Nothing is submitted.

    make up   # or run GigSim and the MCP servers locally
    python -m evals.runners.demo_single_agent [--job-id gs-0136] [--persona ai_ml_engineer]
"""
from __future__ import annotations

import argparse
import asyncio
import json

from agent.mcp_client import AgentTools
from agent.prompts import load_prompt
from evals.runners.architecture_comparison import _final, _job_message, chat_model


async def main_async(job_id: str | None, persona: str) -> None:
    from langgraph.prebuilt import create_react_agent

    tools_access = AgentTools("writer", "demo", persona)
    tools_access.allowed |= {"search_jobs", "get_job", "get_client_history"}  # one agent holding the needed tools
    tools = await tools_access.langchain_tools()
    if job_id is None:
        found = await tools_access.call("search_jobs", {"skills": ["Machine Learning"], "limit": 1})
        job_id = found["jobs"][0]["job_id"]
    job = await tools_access.call("get_job", {"job_id": job_id})
    agent = create_react_agent(chat_model(), tools, prompt=load_prompt("single_agent"))
    state = await agent.ainvoke({"messages": [("user", _job_message(job))]}, {"recursion_limit": 30})
    for message in state["messages"]:
        for call in getattr(message, "tool_calls", []) or []:
            print(f"tool call: {call['name']}({json.dumps(call['args'])[:160]})")
    answer = _final(state["messages"])
    print(f"\nJob {job_id}: {job['title']}\nDecision: {answer['decision']} ({answer.get('reason')})\n")
    print(answer.get("proposal") or "(no proposal)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id")
    parser.add_argument("--persona", default="ai_ml_engineer")
    args = parser.parse_args()
    asyncio.run(main_async(args.job_id, args.persona))


if __name__ == "__main__":
    main()
