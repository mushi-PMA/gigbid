"""Client message threads, with suggested replies and interview slots (approved before sending)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent import runner
from agent.marketplace_port import MarketplacePort
from agent.mcp_client import AgentTools, ServerUnavailable
from apps.api.auth.users import CurrentUser
from apps.api.schemas.models import Accepted, ThreadSummary
from apps.api.tasks import enqueue
from common import db

router = APIRouter(prefix="/api", tags=["messages"])


@router.get("/threads", response_model=list[ThreadSummary])
async def threads(user: dict = CurrentUser) -> list[ThreadSummary]:
    try:
        raw = await MarketplacePort(AgentTools("client_liaison", user["user_id"], user["persona"])).list_threads()
    except ServerUnavailable as error:
        raise HTTPException(503, "marketplace unavailable") from error
    statuses = {r["marketplace_thread"]: r["status"] for r in
                db.fetch_all("SELECT marketplace_thread, status FROM conversations WHERE user_id = %s",
                             (user["user_id"],))}
    return [ThreadSummary(thread_id=t["thread_id"], job_id=t.get("job_id", ""), client_id=t.get("client_id", ""),
                          last_message_at=t.get("last_message_at"), unread=t.get("unread", 0),
                          graph_thread_id=runner.conversation_thread_id(user["user_id"], t["thread_id"]),
                          status=statuses.get(t["thread_id"])) for t in raw]


@router.get("/threads/{thread_id}")
async def thread(thread_id: str, user: dict = CurrentUser) -> dict:
    try:
        messages = await MarketplacePort(AgentTools("client_liaison", user["user_id"], user["persona"])) \
            .list_messages(thread_id)
    except ServerUnavailable as error:
        raise HTTPException(503, "marketplace unavailable") from error
    graph_thread = runner.conversation_thread_id(user["user_id"], thread_id)
    state = await runner.get_thread(graph_thread, user["user_id"], user["persona"])
    values = state["values"]
    return {"thread_id": thread_id, "graph_thread_id": graph_thread,
            "messages": [m.model_dump(mode="json") for m in messages],
            "status": values.get("status"), "analysis": values["analysis"].model_dump() if values.get("analysis")
            else None, "pending_approval": state["pending_approval"]}


@router.post("/threads/{thread_id}/draft", response_model=Accepted, status_code=202)
async def draft_reply(thread_id: str, job_id: str = "", user: dict = CurrentUser) -> Accepted:
    await enqueue("conversation", user["user_id"], thread_id, job_id, job_id=None)
    return Accepted(thread_id=runner.conversation_thread_id(user["user_id"], thread_id), detail="drafting a reply")
