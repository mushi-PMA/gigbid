"""Compliance Guard: enforces the policy pack on proposals and messages before a human sees them.

Pattern rules run first (redact contact details and off-platform payment, catch guarantees and free-work offers);
the small model then reviews what patterns miss. A `block` rule or a model verdict of not allowed blocks the draft,
with the reason shown in the UI.
"""
from __future__ import annotations

import asyncio

import yaml
from langchain_core.runnables import RunnableConfig

from agent.handoffs import ComplianceVerdict, Violation
from agent.nodes.base import node
from agent.nodes.guards import find_violations, redact, rule_actions
from agent.prompts import load_prompt
from common.config import load_policy
from common.llm import complete_json


def check_text(text: str) -> ComplianceVerdict:
    cleaned, removed = redact(text)
    pattern_hits = find_violations(cleaned)
    actions = rule_actions()
    policy_text = yaml.safe_dump([{"id": r["id"], "text": r["text"]} for r in load_policy()["rules"]],
                                 sort_keys=False, width=110)
    user = (f"Pattern rule hits after redaction: {pattern_hits or 'none'}\n\n<text_to_check>\n{cleaned}\n"
            "</text_to_check>")
    verdict = complete_json("compliance", load_prompt("compliance", policy=policy_text), user, ComplianceVerdict)
    verdict.redactions = removed + verdict.redactions
    known = {v.text for v in verdict.violations}
    for rule_id, match in pattern_hits:
        if match not in known:
            verdict.violations.append(Violation(rule_id=rule_id, text=match, fix="remove or rephrase"))
    blocking = [v for v in verdict.violations if actions.get(v.rule_id) == "block"]
    if blocking:
        verdict.allowed = False
        verdict.blocked_reason = f"{blocking[0].rule_id}: '{blocking[0].text[:80]}'"
    elif not verdict.allowed and not verdict.blocked_reason:
        verdict.blocked_reason = verdict.violations[0].text[:120] if verdict.violations else "policy violation"
    if not verdict.cleaned_cover_letter.strip():
        verdict.cleaned_cover_letter = cleaned
    else:  # the model's cleaned text must still pass the redaction rules
        verdict.cleaned_cover_letter, again = redact(verdict.cleaned_cover_letter)
        verdict.redactions += again
    return verdict


@node("compliance")
async def compliance(state: dict, config: RunnableConfig) -> dict:
    draft = state["draft"].model_copy(deep=True)
    verdict = await asyncio.to_thread(check_text, draft.cover_letter)
    draft.cover_letter = verdict.cleaned_cover_letter
    for answer in draft.screening_answers:
        answer_verdict = await asyncio.to_thread(check_text, answer.answer)
        answer.answer = answer_verdict.cleaned_cover_letter
        verdict.violations += answer_verdict.violations
        verdict.redactions += answer_verdict.redactions
        if not answer_verdict.allowed:
            verdict.allowed = False
            verdict.blocked_reason = verdict.blocked_reason or answer_verdict.blocked_reason
    update = {"compliance": verdict, "draft": draft}
    if not verdict.allowed:
        update.update(status="blocked", status_reason=f"Compliance Guard blocked it: {verdict.blocked_reason}")
    return update
