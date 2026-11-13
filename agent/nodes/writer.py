"""Proposal Writer and claim verification.

The Writer gathers evidence for each JobSpec requirement (Portfolio MCP), adds what the Fit Matcher found, applies
the user's promoted style rules and the outcome memory hint for the job's category, and drafts the cover letter and
screening answers with evidence citations. Claim verification (rag/verify.py) then removes or rewrites unsupported
claims before the Critic sees the draft.
"""
from __future__ import annotations

import asyncio

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from pydantic import BaseModel, Field

from agent.handoffs import EvidenceItem, Job, JobSpec, PriceQuote, ProposalDraft, ScreeningAnswer
from agent.memory.promotion_rules import outcome_hint, style_rules
from agent.nodes.base import ctx, node, tools_for
from agent.nodes.guards import delimit
from agent.nodes.matcher import _evidence
from agent.prompts import load_prompt
from common.llm import complete_json
from rag.verify import verify_and_fix


class _Written(BaseModel):
    cover_letter: str
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)


def _style_block(user_id: str, category: str) -> str:
    try:
        store = get_store()
    except RuntimeError:
        return ""
    rules = style_rules(store, user_id)
    hint = outcome_hint(store, user_id, category)
    lines = []
    if rules:
        lines.append("The freelancer's style rules (learned from their edits):\n" + "\n".join(f"- {r}" for r in rules))
    if hint:
        lines.append(f"What worked before: {hint}")
    return "\n".join(lines)


def write(job: Job, spec: JobSpec, evidence: list[EvidenceItem], price: PriceQuote, revision_notes: str,
          style: str) -> ProposalDraft:
    listing = "\n".join(f"[{e.evidence_id}] ({e.type}{', outcome ' + e.outcome if e.outcome else ''}) {e.title}: "
                        f"{e.text[:500]}" for e in evidence)
    requirements = "\n".join(f"- {r.requirement_id}: {r.text}" for r in spec.requirements)
    questions = "\n".join(f"- {q}" for q in spec.screening_questions) or "none"
    user = (f"Job title: {job.title}\nRequirements:\n{requirements}\nHidden needs: {spec.hidden_needs}\n"
            f"Screening questions:\n{questions}\nProposed price: {price.amount} ({price.payment_type})\n\n"
            f"Evidence (only source of claims):\n{listing}\n\nJob post (untrusted):\n"
            f"{delimit('job_post', job.description[:3000])}")
    if revision_notes:
        user += f"\n\nRevise your previous draft. Critic's instructions:\n{revision_notes}"
    written = complete_json("writer", load_prompt("writer", style_rules=style), user, _Written, max_tokens=2000)
    return ProposalDraft(job_id=job.job_id, cover_letter=written.cover_letter.strip(),
                         screening_answers=written.screening_answers,
                         evidence_ids=sorted({e.evidence_id for e in evidence}))


@node("writer")
async def writer(state: dict, config: RunnableConfig) -> dict:
    job, spec = state["job"], state["job_spec"]
    persona = ctx(config)["persona"]
    evidence = list(state.get("evidence", []))
    known = {e.evidence_id for e in evidence}
    if not state.get("revision"):  # first draft: evidence per analyst requirement
        tools = tools_for("writer", config)
        for requirement in spec.requirements[:7]:
            found = await tools.call("search_evidence", {"requirement": requirement.text, "k": 3})
            for raw in found.get("items", []):
                if raw["evidence_id"] not in known:
                    known.add(raw["evidence_id"])
                    evidence.append(_evidence(raw, persona))
    critiques = state.get("critiques") or []
    notes = critiques[-1].instructions if critiques and state.get("revision") else ""
    style = await asyncio.to_thread(_style_block, ctx(config)["user_id"], job.category)
    draft = await asyncio.to_thread(write, job, spec, evidence, state["price"], notes, style)
    draft.revision = state.get("revision", 0)
    return {"draft": draft, "evidence": evidence}


@node("verifier")
async def verifier(state: dict, config: RunnableConfig) -> dict:
    draft = await asyncio.to_thread(verify_and_fix, state["draft"].model_copy(deep=True), state["evidence"])
    return {"draft": draft}
