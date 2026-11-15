"""Worker tasks (Arq on Redis). Scouting and long agent runs execute here, never inside web requests.

Idempotency: jobs are keyed by (user, job id) in `jobs_seen` and enqueued with a deterministic Arq job id, so a worker
restart never analyses a job twice; submissions are idempotent at the marketplace (see agent/nodes/approval.py).
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

from agent import runner
from agent.handoffs import Job
from agent.marketplace_port import MarketplacePort
from agent.mcp_client import AgentTools, ServerUnavailable
from agent.memory.promotion_rules import record_outcome
from agent.memory.store import get_store
from agent.nodes.pricing import connects_spent_this_week, current_week
from agent.nodes.scout import content_key, scout_search
from common import db
from common.config import load_config

STAGE_BY_EVENT = {"proposal_viewed": "viewed", "client_replied": "replied", "interview_requested": "interview",
                  "hired": "hired", "declined": "lost"}
STAGE_ORDER = ["drafted", "submitted", "viewed", "replied", "interview", "hired", "lost"]


def _users() -> list[dict[str, Any]]:
    return db.fetch_all("SELECT u.user_id, u.persona, s.settings FROM users u JOIN user_settings s USING (user_id)")


def _settings(row: dict[str, Any]) -> dict[str, Any]:
    from apps.api.auth.users import DEFAULT_SETTINGS

    return {**DEFAULT_SETTINGS, **(row.get("settings") or {})}


def _passes_filters(job: Job, settings: dict[str, Any]) -> bool:
    filters = settings.get("filters") or {}
    if job.payment_type not in filters.get("payment_types", ["fixed", "hourly"]):
        return False
    budget = job.budget_max or job.budget_min
    return not (budget is not None and budget < float(filters.get("min_budget", 0) or 0))


async def scout_user(ctx: dict, user_id: str, force: bool = False) -> dict[str, Any]:
    row = db.fetch_one("SELECT u.user_id, u.persona, s.settings FROM users u JOIN user_settings s USING (user_id) "
                       "WHERE u.user_id = %s", (user_id,))
    if row is None:
        return {"error": "unknown user"}
    settings = _settings(row)
    now = datetime.now(UTC)
    floor_hours = load_config()["marketplace"]["upwork"]["min_poll_minutes"] / 60 \
        if settings.get("marketplace") == "upwork_live" else 0
    due = []
    for search in settings.get("saved_searches", []):
        last = settings.get("last_scouted", {}).get(search["name"])
        every = max(float(search.get("every_hours", 4)), floor_hours)
        if force or not last or now - datetime.fromisoformat(last) >= timedelta(hours=every):
            due.append(search)
    if not due:
        return {"due": 0}
    port = MarketplacePort(AgentTools("scout", user_id, row["persona"]))
    known = {r["job_id"] for r in db.fetch_all("SELECT job_id FROM jobs_seen WHERE user_id = %s", (user_id,))}
    recent = [{"job_id": r["job_id"], "content_key": r["content_hash"], "client_id": r["summary"].get("client_id"),
               "title": r["summary"].get("title", "")}
              for r in db.fetch_all("SELECT job_id, content_hash, summary FROM jobs_seen WHERE user_id = %s "
                                    "ORDER BY first_seen DESC LIMIT 500", (user_id,))]
    try:
        # no `since` filter: our clock and the marketplace's can differ (GigSim runs a simulated clock), and jobs
        # already seen are skipped by id and content anyway; each search returns the newest jobs first
        new, duplicates = await scout_search(port, due, None, known, recent)
    except ServerUnavailable as error:
        return {"error": f"marketplace unavailable: {error}"}
    from apps.api.tasks import enqueue

    queued = 0
    for job in new:
        summary = {"title": job.title, "client_id": job.client_id, "budget_min": job.budget_min,
                   "budget_max": job.budget_max, "skills": job.skills, "job": job.model_dump(mode="json")}
        if not _passes_filters(job, settings):
            status = "filtered"
        elif queued < int(settings.get("auto_analyze_per_scout", 5)):
            status = "queued"
        else:            # beyond the per-scout cap: listed as new with an Analyze button (keeps model budgets sane)
            status = "new"
        db.execute("INSERT INTO jobs_seen (user_id, job_id, content_hash, status, summary) VALUES (%s, %s, %s, %s, %s) "
                   "ON CONFLICT DO NOTHING", (user_id, job.job_id, content_key(job), status, json.dumps(summary)))
        if status == "queued":
            await enqueue("analyze_job", user_id, job.model_dump(mode="json"), None,
                          job_id=f"analyze:{user_id}:{job.job_id}")
            queued += 1
    for job, original in duplicates:
        summary = {"title": job.title, "client_id": job.client_id, "job": job.model_dump(mode="json"),
                   "status_reason": f"duplicate of {original}"}
        db.execute("INSERT INTO jobs_seen (user_id, job_id, content_hash, status, summary) VALUES "
                   "(%s, %s, %s, 'skipped', %s) ON CONFLICT DO NOTHING",
                   (user_id, job.job_id, content_key(job), json.dumps(summary)))
    stamps = settings.get("last_scouted", {})
    for search in due:
        stamps[search["name"]] = now.isoformat()
    settings.update(last_scouted=stamps, last_scout_time=now.isoformat())
    db.execute("UPDATE user_settings SET settings = %s WHERE user_id = %s", (json.dumps(settings), user_id))
    return {"new": len(new), "duplicates": len(duplicates), "queued": queued}


RUNNING_LOCK = "gigbid:running:{user}:{job}"


async def analyze_job(ctx: dict, user_id: str, job: dict[str, Any], duplicate_of: str | None) -> dict[str, Any]:
    # one run per job at a time: a manual "Analyze" and an automatic one share the same graph thread
    redis, lock = ctx.get("redis"), RUNNING_LOCK.format(user=user_id, job=job["job_id"])
    if redis is not None and not await redis.set(lock, "1", nx=True, ex=900):
        return {"status": "already running"}
    try:
        row = db.fetch_one("SELECT u.persona, s.settings FROM users u JOIN user_settings s USING (user_id) "
                           "WHERE u.user_id = %s", (user_id,))
        settings = _settings(row)
        db.execute("UPDATE jobs_seen SET status = 'running', updated_at = now() WHERE user_id = %s AND job_id = %s",
                   (user_id, job["job_id"]))
        result = await runner.run_bid(user_id, row["persona"], Job.model_validate(job), settings, duplicate_of)
        return {"status": result["state"].get("status"), "pending": result["pending"]}
    finally:
        if redis is not None:
            await redis.delete(lock)


async def resume_thread(ctx: dict, thread_id: str, user_id: str, decision: dict[str, Any]) -> dict[str, Any]:
    row = db.fetch_one("SELECT u.persona, s.settings FROM users u JOIN user_settings s USING (user_id) "
                       "WHERE u.user_id = %s", (user_id,))
    result = await runner.resume(thread_id, user_id, row["persona"], decision, _settings(row))
    state = result["state"]
    if thread_id.startswith("bid:") and state.get("submission", {}).get("proposal_id"):
        submission = state["submission"]
        db.execute("INSERT INTO pipeline_cards (user_id, proposal_id, job_id, title, stage, data) VALUES "
                   "(%s, %s, %s, %s, 'submitted', %s) ON CONFLICT (user_id, proposal_id) DO NOTHING",
                   (user_id, submission["proposal_id"], state["job"].job_id, state["job"].title,
                    json.dumps({"bid": state["price"].amount, "connects": state["price"].connects_cost,
                                "graph_thread_id": thread_id})))
        settings = _settings(row)
        settings["connects_spent_week"] = connects_spent_this_week(settings) + state["price"].connects_cost
        settings["connects_week"] = current_week()
        db.execute("UPDATE user_settings SET settings = %s WHERE user_id = %s", (json.dumps(settings), user_id))
    return {"status": state.get("status")}


async def conversation(ctx: dict, user_id: str, marketplace_thread: str, job_id: str = "") -> dict[str, Any]:
    row = db.fetch_one("SELECT u.persona, s.settings FROM users u JOIN user_settings s USING (user_id) "
                       "WHERE u.user_id = %s", (user_id,))
    result = await runner.run_conversation(user_id, row["persona"], marketplace_thread, job_id, _settings(row))
    return {"status": result["state"].get("status"), "pending": result["pending"]}


async def track_events(ctx: dict, user_id: str) -> dict[str, Any]:
    """Pipeline board, outcome memory and conversations from marketplace events."""
    row = db.fetch_one("SELECT u.persona, s.settings FROM users u JOIN user_settings s USING (user_id) "
                       "WHERE u.user_id = %s", (user_id,))
    settings = _settings(row)
    port = MarketplacePort(AgentTools("tracker", user_id, row["persona"]))
    try:
        events = await port.list_events(settings.get("events_cursor"))
    except ServerUnavailable:
        return {"error": "marketplace unavailable"}
    store = get_store()
    from apps.api.tasks import enqueue

    for event in events:
        stage = STAGE_BY_EVENT.get(event["type"])
        proposal_id = event.get("proposal_id")
        if stage and proposal_id:
            card = db.fetch_one("SELECT stage FROM pipeline_cards WHERE user_id = %s AND proposal_id = %s",
                                (user_id, proposal_id))
            if card and STAGE_ORDER.index(stage) > STAGE_ORDER.index(card["stage"]):
                db.execute("UPDATE pipeline_cards SET stage = %s, updated_at = now() WHERE user_id = %s AND "
                           "proposal_id = %s", (stage, user_id, proposal_id))
            if event["type"] in ("client_replied", "interview_requested", "hired", "declined"):
                features = store.get(("proposal_features", user_id), str(proposal_id))
                if features is not None:
                    record_outcome(store, user_id, str(proposal_id), features.value, event["type"])
        if event["type"] in ("client_replied", "interview_requested") and event.get("thread_id"):
            await enqueue("conversation", user_id, event["thread_id"], event.get("data", {}).get("job_id", ""),
                          job_id=f"conv:{user_id}:{event['event_id']}")
        settings["events_cursor"] = event["at"]
    _expire_silent(user_id, store)
    db.execute("UPDATE user_settings SET settings = %s WHERE user_id = %s", (json.dumps(settings), user_id))
    return {"events": len(events)}


def _expire_silent(user_id: str, store) -> None:
    """Proposals with no reply after 7 days count as ignored for outcome memory and move to lost."""
    rows = db.fetch_all("SELECT proposal_id FROM pipeline_cards WHERE user_id = %s AND stage IN ('submitted', "
                        "'viewed') AND updated_at < now() - interval '7 days'", (user_id,))
    for row in rows:
        db.execute("UPDATE pipeline_cards SET stage = 'lost', updated_at = now() WHERE user_id = %s AND "
                   "proposal_id = %s", (user_id, row["proposal_id"]))
        features = store.get(("proposal_features", user_id), row["proposal_id"])
        if features is not None:
            record_outcome(store, user_id, row["proposal_id"], features.value, "no_reply")


async def recover_interrupted(ctx: dict) -> int:
    """On worker start: clear the locks a stopped worker process left behind and queue its unfinished analyses
    again (one worker per deployment; analysis is idempotent and submission has its own idempotency keys). Without
    this, a redeploy in the middle of an analysis leaves jobs waiting until the old locks expire."""
    from apps.api.tasks import enqueue

    redis = ctx.get("redis")
    if redis is not None:
        for pattern in ("arq:in-progress:*", RUNNING_LOCK.format(user="*", job="*")):
            async for key in redis.scan_iter(match=pattern):
                await redis.delete(key)
    if not os.environ.get("DATABASE_URL"):
        return 0
    rows = db.fetch_all("SELECT user_id, job_id, summary FROM jobs_seen WHERE status = 'running'")
    for row in rows:
        if "job" not in (row["summary"] or {}):
            continue
        db.execute("UPDATE jobs_seen SET status = 'queued' WHERE user_id = %s AND job_id = %s",
                   (row["user_id"], row["job_id"]))
        await enqueue("analyze_job", row["user_id"], row["summary"]["job"], None,
                      job_id=f"analyze:{row['user_id']}:{row['job_id']}:recover:{datetime.now().timestamp():.0f}")
    return len(rows)


async def requeue_degraded(ctx: dict) -> int:
    """Jobs stopped by an unavailable marketplace are retried once it answers again (degraded-mode recovery)."""
    from agent.mcp_client import server_health
    from apps.api.tasks import enqueue

    if not (await server_health()).get("marketplace", False):
        return 0
    rows = db.fetch_all("SELECT user_id, job_id, summary FROM jobs_seen WHERE status = 'needs_attention' AND "
                        "summary->>'status_reason' LIKE 'marketplace_unavailable%%'")
    for row in rows:
        db.execute("UPDATE jobs_seen SET status = 'queued' WHERE user_id = %s AND job_id = %s",
                   (row["user_id"], row["job_id"]))
        await enqueue("analyze_job", row["user_id"], row["summary"]["job"], None,
                      job_id=f"analyze:{row['user_id']}:{row['job_id']}:retry:{datetime.now().timestamp():.0f}")
    return len(rows)


async def scout_all(ctx: dict) -> int:
    for row in _users():
        await scout_user(ctx, row["user_id"])
    return 0


async def track_all(ctx: dict) -> int:
    for row in _users():
        await track_events(ctx, row["user_id"])
    return 0


def worker_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379/0")
