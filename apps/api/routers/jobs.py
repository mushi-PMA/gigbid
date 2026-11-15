"""Job inbox and job detail."""
from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent import runner
from apps.api.auth.users import CurrentUser, get_settings
from apps.api.schemas.models import Accepted, InboxItem, JobDetail
from apps.api.tasks import enqueue
from common import db

router = APIRouter(prefix="/api", tags=["jobs"])


def _dump(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_dump(v) for v in value]
    return value


@router.get("/jobs", response_model=list[InboxItem])
def inbox(user: dict = CurrentUser, status: str | None = Query(None), include_skipped: bool = False,
          limit: int = Query(100, le=500)) -> list[InboxItem]:
    sql = "SELECT job_id, status, first_seen, thread_id, summary FROM jobs_seen WHERE user_id = %s"
    params: list[Any] = [user["user_id"]]
    if status:
        sql += " AND status = %s"
        params.append(status)
    elif not include_skipped:
        sql += " AND status NOT IN ('skipped', 'filtered')"
    rows = db.fetch_all(sql + " ORDER BY first_seen DESC LIMIT %s", (*params, limit))
    items = []
    for row in rows:
        s = row["summary"] or {}
        items.append(InboxItem(job_id=row["job_id"], title=s.get("title", row["job_id"]), status=row["status"],
                               first_seen=row["first_seen"].isoformat(), thread_id=row["thread_id"],
                               fit=s.get("fit"), risk=s.get("risk"), risk_flags=s.get("risk_flags", []),
                               client_quality=s.get("client_quality"), action=s.get("action"), price=s.get("price"),
                               payment_type=s.get("payment_type"), connects_cost=s.get("connects_cost"),
                               status_reason=s.get("status_reason", ""), budget_min=s.get("budget_min"),
                               budget_max=s.get("budget_max"), skills=s.get("skills", [])))
    # ranked by fit: bid recommendations first, then by fit score
    order = {"bid": 0, "watch": 1, None: 2, "skip": 3}
    return sorted(items, key=lambda i: (order.get(i.action, 2), -(i.fit or 0)))


@router.get("/jobs/{job_id}", response_model=JobDetail)
async def job_detail(job_id: str, user: dict = CurrentUser) -> JobDetail:
    row = db.fetch_one("SELECT status, thread_id, summary FROM jobs_seen WHERE user_id = %s AND job_id = %s",
                       (user["user_id"], job_id))
    if row is None:
        raise HTTPException(404, "job not found")
    thread_id = row["thread_id"] or runner.bid_thread_id(user["user_id"], job_id)
    thread = await runner.get_thread(thread_id, user["user_id"], user["persona"])
    values = thread["values"]
    job = values.get("job")
    fresh = row["status"] in ("queued", "running")      # a new run is on its way: the thread still holds the old one
    return JobDetail(job=_dump(job) if job else row["summary"].get("job", {}), thread_id=thread_id,
                     status=row["status"] if fresh else values.get("status", row["status"]),
                     status_reason="" if fresh else values.get("status_reason", ""),
                     **{k: _dump(values.get(k)) for k in ("job_spec", "risk", "fit", "decision", "price", "draft",
                                                          "compliance", "submission")},
                     evidence=_dump(values.get("evidence", [])), critiques=_dump(values.get("critiques", [])),
                     pending_approval=thread["pending_approval"], tokens=values.get("tokens", 0),
                     usd=values.get("usd", 0.0), trace=values.get("trace", []))


@router.post("/jobs/{job_id}/analyze", response_model=Accepted, status_code=202)
async def analyze(job_id: str, user: dict = CurrentUser) -> Accepted:
    row = db.fetch_one("SELECT summary, status FROM jobs_seen WHERE user_id = %s AND job_id = %s",
                       (user["user_id"], job_id))
    if row is None:
        raise HTTPException(404, "job not found")
    if row["status"] in ("awaiting_approval", "approved", "submitted", "running", "queued"):
        raise HTTPException(409, f"this job is {row['status'].replace('_', ' ')}; it cannot be analysed again now")
    if "job" not in (row["summary"] or {}):
        raise HTTPException(409, "the job's details are missing; run the scout again to refresh it")
    db.execute("UPDATE jobs_seen SET status = 'queued' WHERE user_id = %s AND job_id = %s", (user["user_id"], job_id))
    # a fresh id each time: Arq drops a job whose id still has a stored result, so a re-analysis within the result
    # lifetime would never run; the worker's per-job lock stops two runs of the same job at once
    await enqueue("analyze_job", user["user_id"], row["summary"]["job"], None, job_id=f"analyze:{user['user_id']}:"
                  f"{job_id}:manual:{time.time():.0f}")
    return Accepted(thread_id=runner.bid_thread_id(user["user_id"], job_id))


@router.post("/jobs/{job_id}/skip", status_code=204)
def skip(job_id: str, user: dict = CurrentUser) -> None:
    db.execute("UPDATE jobs_seen SET status = 'skipped', summary = summary || %s WHERE user_id = %s AND job_id = %s",
               (json.dumps({"status_reason": "skipped by the freelancer"}), user["user_id"], job_id))


@router.post("/scout/run", response_model=Accepted, status_code=202)
async def scout_now(user: dict = CurrentUser) -> Accepted:
    get_settings(user["user_id"])
    await enqueue("scout_user", user["user_id"], True, job_id=None)
    return Accepted(thread_id="", detail="scouting started")
