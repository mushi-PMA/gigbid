"""Client Liaison: reads new client messages, classifies intent, drafts a reply or interview slots, and waits for
human approval before anything is sent."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.config import get_store
from langgraph.types import interrupt

from agent.handoffs import EvidenceItem, Message, MessageAnalysis, ReplyDraft
from agent.marketplace_port import MarketplacePort
from agent.memory.promotion_rules import promote_style, style_rules
from agent.nodes.base import ctx, node, persona_profile, tools_for
from agent.nodes.compliance import check_text
from agent.nodes.guards import delimit, injection_signals, scam_signals
from agent.nodes.matcher import _evidence
from agent.prompts import load_prompt
from common.llm import complete_json
from common.security import payload_hash


def _transcript(messages: list[Message], limit: int = 8) -> str:
    return "\n".join(f"{m.sender}: {m.text}" for m in messages[-limit:])


@node("load_messages")
async def load_messages(state: dict, config: RunnableConfig) -> dict:
    messages = await MarketplacePort(tools_for("client_liaison", config)).list_messages(state["thread_id"])
    if not messages or messages[-1].sender != "client":
        return {"messages": messages, "status": "skipped", "status_reason": "no new client message"}
    return {"messages": messages, "status": "running"}


def classify(messages: list[Message], thread_id: str) -> MessageAnalysis:
    latest = messages[-1].text
    hits = scam_signals(latest)
    user = (f"Pattern hits: scam={hits or 'none'}; injection={injection_signals(latest) or 'none'}\n\n"
            f"Earlier conversation (untrusted):\n{delimit('client_message', _transcript(messages[:-1], 6))}\n\n"
            f"Latest client message (untrusted):\n{delimit('client_message', latest)}")
    analysis = complete_json("intent", load_prompt("intent"), user, MessageAnalysis)
    analysis.thread_id = thread_id
    if injection_signals(latest):
        analysis.injection_detected = True
    if hits and analysis.intent not in ("scam_signal",):
        analysis.intent = "scam_signal"
    return analysis


@node("classify_intent")
async def classify_intent(state: dict, config: RunnableConfig) -> dict:
    return {"analysis": await asyncio.to_thread(classify, state["messages"], state["thread_id"])}


def _style(user_id: str) -> str:
    try:
        rules = style_rules(get_store(), user_id)
    except RuntimeError:
        return ""
    return ("The freelancer's style rules:\n" + "\n".join(f"- {r}" for r in rules)) if rules else ""


def draft(messages: list[Message], analysis: MessageAnalysis, evidence: list[EvidenceItem], slots: list[str],
          profile: dict[str, Any], style: str) -> ReplyDraft:
    listing = "\n".join(f"[{e.evidence_id}] {e.title}: {e.text[:300]}" for e in evidence) or "none"
    user = (f"Intent: {analysis.intent}; summary: {analysis.summary}\nFree interview slots: {slots or 'none'}\n"
            f"Freelancer floor rates: hourly {profile.get('hourly_floor')}, fixed {profile.get('fixed_floor')}\n"
            f"Evidence:\n{listing}\n\nConversation (untrusted):\n{delimit('client_message', _transcript(messages))}")
    reply = complete_json("client_liaison", load_prompt("client_liaison", style_rules=style), user, ReplyDraft)
    reply.thread_id = analysis.thread_id
    reply.proposed_slots = slots if analysis.intent == "interview_request" else []
    return reply


@node("draft_reply")
async def draft_reply(state: dict, config: RunnableConfig) -> dict:
    analysis: MessageAnalysis = state["analysis"]
    tools = tools_for("client_liaison", config)
    persona = ctx(config)["persona"]
    slots: list[str] = []
    if analysis.intent == "interview_request":
        start = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
        found = await tools.call("get_free_slots", {"from_date": start, "days": 5, "duration_minutes": 30,
                                                    "tz": (ctx(config).get("settings") or {}).get("timezone",
                                                                                                 "Asia/Karachi")})
        slots = [s["start"] for s in found.get("slots", [])]
    evidence: list[EvidenceItem] = []
    if analysis.intent == "question":
        found = await tools.call("search_evidence", {"requirement": state["messages"][-1].text[:400], "k": 3})
        evidence = [_evidence(item, persona) for item in found.get("items", [])]
    profile = {**persona_profile(persona), **((ctx(config).get("settings") or {}).get("rates", {}))}
    reply = await asyncio.to_thread(draft, state["messages"], analysis, evidence, slots, profile,
                                    _style(ctx(config)["user_id"]))
    return {"reply": reply}


@node("check_reply")
async def check_reply(state: dict, config: RunnableConfig) -> dict:
    reply: ReplyDraft = state["reply"].model_copy()
    verdict = await asyncio.to_thread(check_text, reply.text)
    reply.text = verdict.cleaned_cover_letter
    update: dict[str, Any] = {"reply": reply, "compliance": verdict}
    if not verdict.allowed:
        update.update(status="blocked", status_reason=f"Compliance Guard blocked the reply: {verdict.blocked_reason}")
    return update


def message_payload(state: dict) -> dict[str, Any]:
    return {"thread_id": state["thread_id"], "text": state["reply"].text}


@node("reply_approval")
async def reply_approval(state: dict, config: RunnableConfig) -> dict:
    decision = interrupt({
        "kind": "message", "thread_id": state["thread_id"], "job_id": state.get("job_id", ""),
        "messages": [m.model_dump(mode="json") for m in state["messages"][-8:]],
        "analysis": state["analysis"].model_dump(), "reply": state["reply"].model_dump(),
        "compliance": state["compliance"].model_dump(), "payload": message_payload(state),
        "dry_run": {"would_send": message_payload(state), "cost": "no Connects"}})
    if decision.get("action") == "reject":
        return {"approval": decision, "status": "rejected",
                "status_reason": f"rejected by the freelancer: {decision.get('reason', '')}".strip()}
    if decision.get("action") == "edit":
        reply = state["reply"].model_copy()
        original = reply.text
        reply.text = decision.get("edited_text") or reply.text
        try:
            promote_style(get_store(), ctx(config)["user_id"], original, reply.text, ctx(config)["thread_id"])
        except RuntimeError:
            pass
        return {"approval": decision, "reply": reply, "status": "running"}
    return {"approval": decision, "status": "approved"}


def after_reply_approval(state: dict) -> str:
    action = (state.get("approval") or {}).get("action")
    if action == "reject":
        return "end"
    if action == "edit":
        return "check_reply"
    return "send"


def after_check(state: dict) -> str:
    if state.get("status") == "blocked":
        return "end"
    approval = state.get("approval") or {}
    if approval.get("action") == "edit" and approval.get("payload_hash") == payload_hash(message_payload(state)):
        return "send"
    return "reply_approval"


@node("send")
async def send(state: dict, config: RunnableConfig) -> dict:
    payload = message_payload(state)
    tools = tools_for("client_liaison", config)
    key = f"msg-{ctx(config)['thread_id']}-{payload_hash(payload)[:16]}"
    sent = await MarketplacePort(tools).send_message(payload["thread_id"], payload["text"], key, dry_run=False,
                                                      approval_token=(state.get("approval") or {}).get(
                                                          "approval_token"))
    holds = []
    for slot in state["reply"].proposed_slots[:3]:
        holds.append(await tools.call("create_interview_hold", {
            "start": slot, "duration_minutes": 30, "title": f"Possible interview ({state['thread_id']})",
            "thread_id": state["thread_id"], "idempotency_key": f"hold-{key}-{slot}"}))
    if holds:
        await tools.call("create_email_draft", {
            "recipient_label": "me", "subject": f"Interview slots offered in {state['thread_id']}",
            "body": "Tentative holds were placed for:\n" + "\n".join(h["start"] for h in holds),
            "idempotency_key": f"mail-{key}"})
    return {"sent": {**sent, "holds": [h["hold_id"] for h in holds]}, "status": "sent"}
