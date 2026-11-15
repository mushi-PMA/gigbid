"""Critic: checks grounding, personalisation and length; sends a draft back at most `max_revisions` times."""
from __future__ import annotations

import asyncio
import re

from langchain_core.runnables import RunnableConfig

from agent.handoffs import Critique, Job, ProposalDraft
from agent.nodes.base import node
from agent.nodes.guards import delimit, word_count
from agent.prompts import load_prompt
from common.config import load_config
from common.llm import complete_json

CITATION = re.compile(r"\[[a-z_]+:[^\]]+\]")


def structural_issues(draft: ProposalDraft, job: Job) -> list[str]:
    """Checks that need no model."""
    issues = []
    words = word_count(draft.cover_letter)
    if words < 120 or words > 220:
        issues.append(f"cover letter is {words} words; it must be 120 to 220")
    if not CITATION.search(draft.cover_letter):
        issues.append("no evidence citation in the cover letter")
    answered = {a.question.strip().lower() for a in draft.screening_answers}
    for question in job.screening_questions:
        if question.strip().lower() not in answered:
            issues.append(f"screening question not answered: {question[:80]}")
    if draft.unsupported_after_verification:
        issues.append(f"{draft.unsupported_after_verification} claim(s) still unsupported after verification")
    return issues


def critique(draft: ProposalDraft, job: Job) -> Critique:
    t = load_config()["thresholds"]
    claims = "\n".join(f"- [{c.status}] {c.text} -> {c.evidence_ids}" for c in draft.claims) or "none"
    answers = "\n".join(f"Q: {a.question}\nA: {a.answer}" for a in draft.screening_answers) or "none"
    user = (f"Job title: {job.title}\nJob post (untrusted):\n{delimit('job_post', job.description[:2500])}\n\n"
            f"Draft cover letter:\n{draft.cover_letter}\n\nScreening answers:\n{answers}\n\n"
            f"Claim verification results:\n{claims}")
    result = complete_json("critic", load_prompt("critic", min_personalisation=str(t["critic_min_personalisation"])),
                           user, Critique)
    hard = structural_issues(draft, job)
    if hard:
        result.issues = hard + result.issues
        result.length_ok = not any("words" in i for i in hard)
        result.grounding_ok = result.grounding_ok and not any("unsupported" in i or "citation" in i for i in hard)
        result.approve = False
        result.instructions = ("Fix: " + "; ".join(hard) + ". " + result.instructions).strip()
    if result.personalisation < t["critic_min_personalisation"]:
        result.approve = False
    return result


@node("critic")
async def critic(state: dict, config: RunnableConfig) -> dict:
    result = await asyncio.to_thread(critique, state["draft"], state["job"])
    return {"critiques": [result], "revision": state.get("revision", 0) + (0 if result.approve else 1)}


def only_length(critique: Critique) -> bool:
    """Grounded and personal, and too short: what is left when claim verification removed unsupported sentences."""
    return (not critique.length_ok and critique.grounding_ok
            and critique.personalisation >= load_config()["thresholds"]["critic_min_personalisation"])


def after_critic(state: dict) -> str:
    """Back to the Writer while the Critic rejects and revisions remain; otherwise on to Compliance. When the Writer
    has already had one chance to fix the length and length is the only complaint left, the draft goes on to the
    human: on jobs with thin evidence another pass only puts the unsupported sentences back and spends the token
    budget (docs/FAILURES.md, row 13)."""
    last = state["critiques"][-1]
    revision = state.get("revision", 0)
    if last.approve or revision > load_config()["budgets"]["max_revisions"]:
        return "compliance"
    if revision >= 2 and only_length(last):
        return "compliance"
    return "writer"
