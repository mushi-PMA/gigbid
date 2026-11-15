"""R&D question C: is the multi-agent design worth it?

On fixed dev jobs (the brief asks for 50; docs/HYPOTHESES.md records the size we ran), compare (a) one ReAct agent
holding all tools, (b) a prebuilt supervisor (langgraph-supervisor) with three tool-using workers, and (c) GigBid's
hand-built graph. All three use the same MCP tools, the same models (node `tool_agent` for a and b) and the same
simulated clients. Reported: bid-or-skip accuracy, unsupported claims per proposal (same verifier and evidence pool
for all), policy violations left in the final text, violations the Compliance Guard caught, GigSim reply rate, tokens
and latency.

    python -m evals.runners.architecture_comparison --jobs 50
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from contextlib import AsyncExitStack

from agent.inmemory import load_servers
from agent.nodes.guards import find_violations
from agent.prompts import load_prompt
from common.config import load_config, model_profile
from common.llm import extract_json, price_usd
from evals.runners.common import PERSONAS, RESULTS, enable_cache, load_set, percentile, write_result
from evals.runners.harness import EvalMarketplace, install, run_job
from rag.retriever import Retriever, get_index
from rag.verify import unsupported_count, verify_text

MARKET_TOOLS = {"get_job", "get_client_history", "get_market_pricing", "get_connects_balance"}
PORTFOLIO_TOOLS = {"search_evidence", "get_case_study", "list_skills"}


def baseline_endpoint() -> tuple[dict, str]:
    """The endpoint and model id the LangChain baselines use: the first pool endpoint with a key that serves the
    tool_agent size (env ARCH_ENDPOINT picks one by name). Same weights as GigBid's graph uses for that role."""
    size = model_profile()["nodes"]["tool_agent"]
    wanted = os.environ.get("ARCH_ENDPOINT")
    for endpoint in load_config()["models"]["endpoints"]:
        if size in endpoint["models"] and os.environ.get(endpoint["api_key_env"]) \
                and wanted in (None, endpoint["name"]):
            return endpoint, endpoint["models"][size]
    raise RuntimeError(f"no endpoint with a key serves '{size}'")


def chat_model():
    from langchain_openai import ChatOpenAI

    endpoint, model = baseline_endpoint()
    key = os.environ[endpoint["api_key_env"]].split(",")[0].strip()     # one key when several are listed
    return ChatOpenAI(model=model, base_url=endpoint["base_url"].format_map(os.environ), api_key=key,
                      temperature=0, max_tokens=2000, max_retries=8, timeout=load_config()["models"]["timeout_seconds"],
                      extra_body=endpoint.get("extra_body") or None)       # same request settings as the graph


async def mcp_tools(stack: AsyncExitStack) -> list:
    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp.shared.memory import create_connected_server_and_client_session

    tools = []
    for name in ("marketplace", "portfolio"):
        session = await stack.enter_async_context(
            create_connected_server_and_client_session(load_servers()[name]._mcp_server))
        tools += [t for t in await load_mcp_tools(session) if t.name in MARKET_TOOLS | PORTFOLIO_TOOLS]
    return tools


def _usage(messages) -> tuple[int, float]:
    model = baseline_endpoint()[1]
    tin = sum((getattr(m, "usage_metadata", None) or {}).get("input_tokens", 0) for m in messages)
    tout = sum((getattr(m, "usage_metadata", None) or {}).get("output_tokens", 0) for m in messages)
    return tin + tout, price_usd(model, tin, tout)


def _final(messages) -> dict:
    for message in reversed(messages):
        content = message.content if isinstance(message.content, str) else " ".join(
            part.get("text", "") for part in message.content if isinstance(part, dict))
        try:
            value = extract_json(content)
            if isinstance(value, dict) and "decision" in value:
                return value
        except ValueError:
            continue
    return {"decision": "skip", "reason": "no final answer", "price": None, "proposal": None}


def _job_message(job: dict) -> str:
    return (f"Job id: {job['job_id']}. Client id: {job.get('client_id')}. Title: {job['title']}\n"
            f"<job_post>\n{job['description'][:3000]}\n</job_post>")


async def run_react(job: dict, tools: list) -> dict:
    from langgraph.prebuilt import create_react_agent

    agent = create_react_agent(chat_model(), tools, prompt=load_prompt("single_agent"))
    started = time.perf_counter()
    state = await agent.ainvoke({"messages": [("user", _job_message(job))]}, {"recursion_limit": 30})
    tokens, usd = _usage(state["messages"])
    return {**_final(state["messages"]), "seconds": time.perf_counter() - started, "tokens": tokens, "usd": usd}


async def run_supervisor(job: dict, tools: list) -> dict:
    from langgraph.prebuilt import create_react_agent
    from langgraph_supervisor import create_supervisor

    model = chat_model()
    market = create_react_agent(model, [t for t in tools if t.name in MARKET_TOOLS],
                                prompt=load_prompt("supervisor_market"), name="market_researcher")
    portfolio = create_react_agent(model, [t for t in tools if t.name in PORTFOLIO_TOOLS],
                                   prompt=load_prompt("supervisor_portfolio"), name="portfolio_researcher")
    writer = create_react_agent(model, [], prompt=load_prompt("supervisor_writer"), name="proposal_writer")
    graph = create_supervisor([market, portfolio, writer], model=model, prompt=load_prompt("supervisor"),
                              output_mode="full_history").compile()
    started = time.perf_counter()
    state = await graph.ainvoke({"messages": [("user", _job_message(job))]}, {"recursion_limit": 60})
    tokens, usd = _usage(state["messages"])
    return {**_final(state["messages"]), "seconds": time.perf_counter() - started, "tokens": tokens, "usd": usd}


async def patient(runner, job: dict, tools: list) -> dict:
    """Run a baseline, starting it again after a provider rate limit (a free-tier limit is not a design failure);
    any other error, or a limit that lasts past the last wait, is raised and reported."""
    for wait in (60, 120, 300, 600, 900, None):
        try:
            return await runner(job, tools)
        except Exception as error:
            if wait is None or ("429" not in str(error) and "RateLimit" not in type(error).__name__):
                raise
            await asyncio.sleep(wait)


def previous_rows() -> dict[tuple[str, str], dict]:
    """Rows of the last run that finished without an error, to resume a run that hit provider limits."""
    path = RESULTS / "architecture_comparison.json"
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", []) if path.exists() else []
    return {(r["design"], r["job_id"]): r for r in rows if "error" not in r}


def evidence_pool(persona: str, job: dict, cited: str) -> list:
    """Same evidence for every design: top-12 shipped retrieval for the job plus every document the text cites."""
    pool = Retriever(persona, k=12).search_text(f"{job['title']}\n{job['description']}", 12)
    known = {e.evidence_id for e in pool}
    index = get_index(persona)
    from rag.index.store import Hit
    from rag.variants.base import to_items

    for chunk in index.chunks:
        if chunk.evidence_id in cited and chunk.evidence_id not in known:
            pool += to_items([Hit(chunk, 0.0)], persona, 1)
            known.add(chunk.evidence_id)
    return pool


async def score_text(persona: str, job: dict, market: EvalMarketplace, decision: str, proposal: str | None,
                     price: float | None) -> dict:
    out = {"pred_bid": decision == "bid", "violations_left": 0, "unsupported": None, "replied": None}
    if decision == "bid" and proposal:
        claims = await asyncio.to_thread(verify_text, proposal, evidence_pool(persona, job, proposal))
        out["unsupported"] = unsupported_count(claims)
        out["violations_left"] = len(find_violations(proposal))
        body = {"job_id": job["job_id"], "cover_letter": proposal, "screening_answers": [],
                "bid_amount": float(price or job.get("budget_max") or 100), "payment_type": job["payment_type"]}
        draft = await market.create_proposal_draft(body, "k", False)
        await market.submit_proposal(draft["proposal_id"], "k", False)
        out["replied"] = bool(market.outcomes.get(job["job_id"], {}).get("replied"))
    return out


async def evaluate(n_jobs: int, resume: bool = False) -> dict:
    per = {p: n_jobs // len(PERSONAS) + (1 if i < n_jobs % len(PERSONAS) else 0) for i, p in enumerate(PERSONAS)}
    rows, done = [], previous_rows() if resume else {}
    for persona in PERSONAS:
        items = [i for i in load_set(persona, "dev") if not i["gold"].get("duplicate")][: per[persona]]
        async with AsyncExitStack() as stack:
            for design in ("single_react", "supervisor", "graph"):
                market = EvalMarketplace([i["job"] for i in items])
                install(market, persona)
                tools = await mcp_tools(stack) if design != "graph" else []
                for item in items:
                    job, gold = item["job"], item["gold"]
                    if (design, job["job_id"]) in done:
                        rows.append(done[(design, job["job_id"])])
                        continue
                    try:
                        if design == "graph":
                            result = await run_job(job, persona, approve=True)
                            state = result["state"]
                            bid = bool(state.get("decision") and state["decision"].action == "bid")
                            draft = state.get("draft")
                            row = {"pred_bid": bid, "seconds": result["seconds"], "tokens": result["tokens"],
                                   "usd": result["usd"],
                                   "violations_caught": len(state["compliance"].violations)
                                   if state.get("compliance") else 0}
                            if draft is not None and result["drafted"]:
                                claims = await asyncio.to_thread(verify_text, draft.cover_letter,
                                                                 evidence_pool(persona, job, draft.cover_letter))
                                row.update(unsupported=unsupported_count(claims),
                                           violations_left=len(find_violations(draft.cover_letter)),
                                           replied=bool(market.outcomes.get(job["job_id"], {}).get("replied")))
                        else:
                            runner = run_react if design == "single_react" else run_supervisor
                            answer = await patient(runner, job, tools)
                            row = {"seconds": answer["seconds"], "tokens": answer["tokens"], "usd": answer["usd"],
                                   "violations_caught": 0,
                                   **await score_text(persona, job, market, answer.get("decision", "skip"),
                                                      answer.get("proposal"), answer.get("price"))}
                    except Exception as error:  # a crashed run counts as a wrong skip, and is reported
                        row = {"pred_bid": False, "error": f"{type(error).__name__}: {str(error)[:200]}",
                               "seconds": 0, "tokens": 0, "usd": 0}
                    rows.append({"design": design, "persona": persona, "job_id": job["job_id"],
                                 "job_type": gold.get("job_type"), "kind": job.get("kind", "regular"),
                                 "gold_bid": bool(gold.get("bid")), **row})
    return summarise(rows)


def summarise(rows: list[dict]) -> dict:
    out = {}
    for design in ("single_react", "supervisor", "graph"):
        rs = [r for r in rows if r["design"] == design]
        written = [r for r in rs if r.get("unsupported") is not None]
        replied = [r for r in rs if r.get("replied") is not None]
        by_type = {}
        for job_type in sorted({r["job_type"] for r in rs if r["job_type"]}):
            group = [r for r in rs if r["job_type"] == job_type]
            by_type[job_type] = round(sum(r["pred_bid"] == r["gold_bid"] for r in group) / len(group), 3)
        out[design] = {
            "n": len(rs), "bid_or_skip_accuracy": round(sum(r["pred_bid"] == r["gold_bid"] for r in rs) / len(rs), 4),
            "unsupported_claims_per_proposal": round(sum(r["unsupported"] for r in written) / len(written), 3)
            if written else None,
            "violations_left_in_output": sum(r.get("violations_left", 0) for r in rs),
            "violations_caught": sum(r.get("violations_caught", 0) for r in rs),
            "scams_bid_on": sum(1 for r in rs if r["kind"] == "scam" and r["pred_bid"]),
            "injections_bid_on": sum(1 for r in rs if r["kind"] == "injection" and r["pred_bid"]),
            "gigsim_reply_rate": round(sum(r["replied"] for r in replied) / len(replied), 4) if replied else None,
            "mean_tokens": round(sum(r["tokens"] for r in rs) / len(rs)),
            "mean_usd": round(sum(r["usd"] for r in rs) / len(rs), 6),
            "p50_seconds": percentile([r["seconds"] for r in rs], 0.5),
            "p95_seconds": percentile([r["seconds"] for r in rs], 0.95),
            "errors": sum(1 for r in rs if "error" in r), "accuracy_by_job_type": by_type}
    return {"designs": out, "rows": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=50)
    parser.add_argument("--resume", action="store_true", help="keep the last run's rows that had no error")
    args = parser.parse_args()
    enable_cache("architectures")
    summary = asyncio.run(evaluate(args.jobs, args.resume))
    print(json.dumps(summary["designs"], indent=1))
    write_result("architecture_comparison", {"n_jobs": args.jobs, **summary})


if __name__ == "__main__":
    main()
