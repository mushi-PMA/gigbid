"""Approvals: list pending interrupts, approve / edit / reject (resumes the paused graph thread), and regenerate one
paragraph of a proposal draft. A pending approval lives in the checkpointer, so a page refresh never loses it."""
from __future__ import annotations

import asyncio
import difflib

from fastapi import APIRouter, HTTPException

from agent import runner
from agent.prompts import load_prompt
from apps.api.auth.users import CurrentUser
from apps.api.schemas.models import Accepted, ApprovalIn, ApprovalItem, RegenerateIn, RegenerateOut
from apps.api.tasks import enqueue
from common import db
from common.llm import complete
from common.payloads import edited_payload
from common.security import mint_approval_token, payload_hash

router = APIRouter(prefix="/api", tags=["approvals"])


def _owned(thread_id: str, user_id: str) -> None:
    if thread_id.split(":")[1:2] != [user_id]:
        raise HTTPException(404, "not found")


@router.get("/approvals", response_model=list[ApprovalItem])
async def pending(user: dict = CurrentUser) -> list[ApprovalItem]:
    bids = db.fetch_all("SELECT thread_id, summary, updated_at FROM jobs_seen WHERE user_id = %s AND "
                        "status = 'awaiting_approval' ORDER BY updated_at DESC", (user["user_id"],))
    conversations = db.fetch_all("SELECT graph_thread_id AS thread_id, updated_at FROM conversations WHERE "
                                 "user_id = %s AND status = 'awaiting_approval' ORDER BY updated_at DESC",
                                 (user["user_id"],))
    items = []
    for row in bids + conversations:
        thread = await runner.get_thread(row["thread_id"], user["user_id"], user["persona"])
        request = thread["pending_approval"]
        if request is None:
            continue
        title = request["job"]["title"] if request["kind"] == "proposal" else f"Reply in {request['thread_id']}"
        items.append(ApprovalItem(thread_id=row["thread_id"], kind=request["kind"], title=title,
                                  created_at=row["updated_at"].isoformat(), request=request))
    return items


@router.get("/approvals/{thread_id}", response_model=ApprovalItem)
async def one(thread_id: str, user: dict = CurrentUser) -> ApprovalItem:
    _owned(thread_id, user["user_id"])
    thread = await runner.get_thread(thread_id, user["user_id"], user["persona"])
    request = thread["pending_approval"]
    if request is None:
        raise HTTPException(404, "nothing is waiting for approval in this thread")
    title = request["job"]["title"] if request["kind"] == "proposal" else f"Reply in {request['thread_id']}"
    return ApprovalItem(thread_id=thread_id, kind=request["kind"], title=title, request=request)


@router.post("/approvals/{thread_id}", response_model=Accepted, status_code=202)
async def decide(thread_id: str, body: ApprovalIn, user: dict = CurrentUser) -> Accepted:
    _owned(thread_id, user["user_id"])
    thread = await runner.get_thread(thread_id, user["user_id"], user["persona"])
    request = thread["pending_approval"]
    if request is None:
        raise HTTPException(409, "this approval was already handled")
    if body.action == "reject" and not body.reason.strip():
        raise HTTPException(422, "say why you reject it; the reason is kept for analytics")
    decision = {"action": body.action, "reason": body.reason, "user_id": user["user_id"]}
    diff = ""
    if body.action in ("approve", "edit"):
        if request["kind"] == "proposal":
            payload = request["payload"]
            if body.action == "edit":
                payload = edited_payload(payload, body.edited_text, body.edited_answers)
                diff = "\n".join(difflib.unified_diff(request["payload"]["cover_letter"].splitlines(),
                                                      payload["cover_letter"].splitlines(), lineterm=""))
            token = mint_approval_token(user["user_id"], "submit_proposal", payload["job_id"], payload)
        else:
            payload = {"thread_id": request["thread_id"],
                       "text": body.edited_text if body.action == "edit" and body.edited_text
                       else request["payload"]["text"]}
            if body.action == "edit":
                diff = "\n".join(difflib.unified_diff(request["payload"]["text"].splitlines(),
                                                      payload["text"].splitlines(), lineterm=""))
            token = mint_approval_token(user["user_id"], "send_message", payload["thread_id"], payload)
        decision.update(approval_token=token, payload_hash=payload_hash(payload),
                        edited_text=body.edited_text, edited_answers=body.edited_answers)
    db.execute("INSERT INTO approvals_log (user_id, thread_id, kind, action, reason, diff) VALUES "
               "(%s, %s, %s, %s, %s, %s)", (user["user_id"], thread_id, request["kind"], body.action, body.reason,
                                            diff))
    if thread_id.startswith("bid:"):
        db.execute("UPDATE jobs_seen SET status = 'running' WHERE user_id = %s AND thread_id = %s",
                   (user["user_id"], thread_id))
    await enqueue("resume_thread", thread_id, user["user_id"], decision,
                  job_id=f"resume:{thread_id}:{payload_hash(decision)[:12]}")
    return Accepted(thread_id=thread_id, detail=f"{body.action} recorded")


@router.post("/proposals/{thread_id}/regenerate", response_model=RegenerateOut)
async def regenerate_paragraph(thread_id: str, body: RegenerateIn, user: dict = CurrentUser) -> RegenerateOut:
    """Rewrite one paragraph of the pending draft with the same evidence (the user then approves or edits)."""
    _owned(thread_id, user["user_id"])
    thread = await runner.get_thread(thread_id, user["user_id"], user["persona"])
    request = thread["pending_approval"]
    if request is None or request["kind"] != "proposal":
        raise HTTPException(404, "no proposal waiting for approval")
    paragraphs = [p for p in request["draft"]["cover_letter"].split("\n\n")]
    if body.paragraph_index >= len(paragraphs):
        raise HTTPException(422, "no such paragraph")
    evidence = "\n".join(f"[{e['evidence_id']}] {e['title']}: {e['text'][:400]}"
                         for claim in request["claims"] for e in claim.get("evidence", []))
    user_text = load_prompt("regenerate_paragraph",
                            instruction=f"Instruction: {body.instruction}" if body.instruction else "",
                            evidence=evidence, proposal=request["draft"]["cover_letter"],
                            paragraph=paragraphs[body.paragraph_index])
    text = await asyncio.to_thread(complete, "writer", load_prompt("writer", style_rules=""), user_text, max_tokens=500)
    return RegenerateOut(paragraph_index=body.paragraph_index, text=text.strip())
