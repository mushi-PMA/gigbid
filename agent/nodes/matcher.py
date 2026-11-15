"""Fit Matcher: maps every requirement to portfolio evidence through the Portfolio MCP server, then scores fit.

It runs in parallel with the Job Analyst, so it decomposes the post itself (V1) instead of waiting for the JobSpec.
Retrieval uses the shipped RAG variant inside the Portfolio server (`search_evidence`).
"""
from __future__ import annotations

import asyncio

from langchain_core.runnables import RunnableConfig

from agent.handoffs import EvidenceItem, FitReport, Job
from agent.nodes.base import node, tools_for
from agent.nodes.guards import delimit
from agent.prompts import load_prompt
from common.llm import complete_json
from rag.variants.v1_decomposition import decompose


def _evidence(raw: dict, persona: str) -> EvidenceItem:
    return EvidenceItem(evidence_id=raw["evidence_id"], persona=persona, type=raw.get("type", "case_study"),
                        project=raw.get("project", ""), title=raw.get("title", ""), text=raw.get("excerpt", ""),
                        skills=raw.get("skills", []), date=raw.get("date", ""), outcome=raw.get("outcome", ""),
                        client_industry=raw.get("client_industry", ""), source=raw.get("source", ""),
                        score=raw.get("score", 0.0))


def score_fit(job: Job, requirements: list[str], per_requirement: dict[str, list[EvidenceItem]]) -> FitReport:
    blocks = []
    for number, requirement in enumerate(requirements, start=1):
        items = per_requirement.get(f"r{number}", [])
        listing = "\n".join(f"  [{e.evidence_id}] ({e.type}) {e.title}: {e.text[:350]}" for e in items) or "  none"
        blocks.append(f"r{number}: {requirement}\n{listing}")
    user = (f"Job: {job.title}\nTagged skills: {', '.join(job.skills)}\n\n" + "\n\n".join(blocks)
            + f"\n\nJob post (untrusted):\n{delimit('job_post', job.description[:2500])}")
    # one match per requirement plus the model's own reasoning needs more room than the default answer length
    report = complete_json("fit_matcher", load_prompt("fit_matcher"), user, FitReport, max_tokens=3500)
    report.job_id = job.job_id
    known = {e.evidence_id for items in per_requirement.values() for e in items}
    for match in report.matches:
        match.evidence_ids = [i for i in match.evidence_ids if i in known]
        if not match.evidence_ids:
            match.strength = "none"
    report.evidence_ids = sorted({i for m in report.matches for i in m.evidence_ids})
    return report


@node("fit_matcher")
async def fit_matcher(state: dict, config: RunnableConfig) -> dict:
    job: Job = state["job"]
    persona = config["configurable"]["persona"]
    requirements = await asyncio.to_thread(decompose, f"{job.title}\n{job.description}")
    tools = tools_for("fit_matcher", config)
    # one search per requirement, all at once (each is independent)
    found = await asyncio.gather(*(tools.call("search_evidence", {"requirement": r, "k": 4}) for r in requirements))
    per_requirement: dict[str, list[EvidenceItem]] = {
        f"r{number}": [_evidence(item, persona) for item in result.get("items", [])]
        for number, result in enumerate(found, start=1)}
    report = await asyncio.to_thread(score_fit, job, requirements, per_requirement)
    seen: set[str] = set()
    evidence = [e for items in per_requirement.values() for e in items
                if not (e.evidence_id in seen or seen.add(e.evidence_id))]
    return {"fit": report, "evidence": evidence}
