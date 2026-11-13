"""Human approval (LangGraph interrupt) and exactly-once submission.

- prepare_approval: asks the marketplace for a dry_run of the draft (exactly what would be sent and what it costs).
- approval: interrupt() with everything the human needs: draft, the evidence behind every claim, the risk report,
  the price rationale, Critic and Compliance notes and the dry_run preview. Resumes with approve, edit or reject.
- learn_from_edit: diffs the human edit against the draft and records style-memory candidates (promotion rule).
- submit: creates the draft and submits it with the approval token. The idempotency key is derived from the thread
  and the approved payload, so a crash and resume, or a retried call, never submits twice or spends Connects twice.
"""
from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.types import interrupt

from agent.handoffs import ProposalDraft
from agent.marketplace_port import MarketplacePort
from agent.mcp_client import ToolError
from agent.memory.promotion_rules import promote_style, proposal_features
from agent.nodes.base import ctx, node, tools_for
from common.payloads import draft_payload
from common.security import payload_hash


def payload_for(state: dict) -> dict[str, Any]:
    draft: ProposalDraft = state["draft"]
    return draft_payload(state["job"].job_id, draft.cover_letter,
                         [{"question": a.question, "answer": a.answer} for a in draft.screening_answers],
                         round(float(state["price"].amount), 2), state["price"].payment_type)


def idempotency_key(thread_id: str, payload: dict[str, Any], step: str) -> str:
    return f"{step}-{thread_id}-{payload_hash(payload)[:16]}"


@node("prepare_approval")
async def prepare_approval(state: dict, config: RunnableConfig) -> dict:
    payload = payload_for(state)
    port = MarketplacePort(tools_for("submitter", config))
    preview = await port.create_proposal_draft(payload, idempotency_key(ctx(config)["thread_id"], payload, "draft"),
                                               dry_run=True)
    return {"dry_run_preview": {"payload": payload, "marketplace": preview,
                                "connects_cost": state["price"].connects_cost}, "status": "awaiting_approval"}


def approval_request(state: dict) -> dict[str, Any]:
    draft: ProposalDraft = state["draft"]
    evidence = {e.evidence_id: e.model_dump() for e in state.get("evidence", [])}
    return {
        "kind": "proposal",
        "job": state["job"].model_dump(mode="json"),
        "draft": draft.model_dump(mode="json"),
        "claims": [{**c.model_dump(), "evidence": [evidence[i] for i in c.evidence_ids if i in evidence]}
                   for c in draft.claims],
        "risk": state["risk"].model_dump(),
        "fit": state["fit"].model_dump(),
        "decision": state["decision"].model_dump(),
        "price": state["price"].model_dump(),
        "critique": state["critiques"][-1].model_dump() if state.get("critiques") else None,
        "compliance": state["compliance"].model_dump() if state.get("compliance") else None,
        "dry_run": state.get("dry_run_preview"),
        "payload": payload_for(state),
    }


@node("approval")
async def approval(state: dict, config: RunnableConfig) -> dict:
    decision = interrupt(approval_request(state))  # pauses here until the human acts in the UI
    action = decision.get("action")
    if action == "reject":
        return {"approval": decision, "status": "rejected",
                "status_reason": f"rejected by the freelancer: {decision.get('reason', '')}".strip()}
    if action == "edit":
        draft = state["draft"].model_copy(deep=True)
        before = draft.cover_letter
        draft.cover_letter = decision.get("edited_text") or draft.cover_letter
        for answer, text in zip(draft.screening_answers, decision.get("edited_answers") or []):
            answer.answer = text or answer.answer
        return {"approval": {**decision, "original_text": before}, "draft": draft, "status": "running"}
    return {"approval": decision, "status": "approved"}


def after_approval(state: dict) -> str:
    action = (state.get("approval") or {}).get("action")
    return {"reject": "end", "edit": "learn_from_edit"}.get(action, "submit")


@node("learn_from_edit")
async def learn_from_edit(state: dict, config: RunnableConfig) -> dict:
    approval_value = state["approval"]
    try:
        promoted = await asyncio.to_thread(promote_style, get_store(), ctx(config)["user_id"],
                                           approval_value.get("original_text", ""), state["draft"].cover_letter,
                                           ctx(config)["thread_id"])
    except RuntimeError:  # no store configured (offline evaluation)
        promoted = []
    return {"approval": {**approval_value, "promoted_style_rules": promoted}}


def after_edit_check(state: dict) -> str:
    """After an edit is re-checked by Compliance: submit if it passed unchanged, else ask the human again."""
    if state.get("status") == "blocked":
        return "end"
    approved = (state.get("approval") or {}).get("payload_hash")
    return "submit" if approved and approved == payload_hash(payload_for(state)) else "prepare_approval"


@node("submit")
async def submit(state: dict, config: RunnableConfig) -> dict:
    payload = payload_for(state)
    token = (state.get("approval") or {}).get("approval_token")
    thread_id = ctx(config)["thread_id"]
    port = MarketplacePort(tools_for("submitter", config))
    try:
        draft = await port.create_proposal_draft(payload, idempotency_key(thread_id, payload, "draft"),
                                                 dry_run=False, approval_token=token)
        proposal_id = draft.get("proposal_id") or draft.get("id")
        result = await port.submit_proposal(proposal_id, payload["job_id"], payload,
                                            idempotency_key(thread_id, payload, "submit"), dry_run=False,
                                            approval_token=token)
    except ToolError as error:
        if error.error == "approval_required":
            return {"status": "awaiting_approval", "status_reason": f"approval no longer valid: {error.detail}"}
        return {"status": "blocked", "status_reason": f"marketplace refused the proposal: {error.detail}",
                "submission": {"error": error.error, "detail": error.detail}}
    features = proposal_features(state["job"].category, payload["cover_letter"],
                                 [e.type for e in state.get("evidence", []) if e.evidence_id in
                                  {i for c in state["draft"].claims for i in c.evidence_ids}],
                                 payload["bid_amount"], state["price"].market_p50)
    try:
        get_store().put(("proposal_features", ctx(config)["user_id"]), str(proposal_id),
                        {**features, "job_id": payload["job_id"], "title": state["job"].title})
    except RuntimeError:
        pass
    return {"submission": {"proposal_id": proposal_id, **result}, "status": "submitted",
            "status_reason": f"submitted; {result.get('connects_spent', state['price'].connects_cost)} Connects"}
