"""Scout: runs saved searches on a schedule, removes duplicates and queues new jobs (worker), and hands one job into
the bid graph (intake node)."""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any

from langchain_core.runnables import RunnableConfig

from agent.handoffs import Job
from agent.marketplace_port import MarketplacePort
from agent.nodes.base import ctx, node, tools_for


def content_key(job: Job) -> str:
    """Hash of the normalised title and description: reposts with small edits get the same key."""
    text = f"{job.title} {job.description}".lower()
    text = re.sub(r"[^a-z ]+", " ", text)
    words = [w for w in text.split() if len(w) > 2][:80]
    return hashlib.sha1(" ".join(words).encode()).hexdigest()[:16]


def is_near_duplicate(job: Job, recent: list[dict[str, Any]]) -> str | None:
    """Job id of an earlier post this one repeats (same normalised text, or same client with a very similar title)."""
    key = content_key(job)
    for seen in recent:
        if seen["job_id"] == job.job_id:
            continue
        if seen.get("content_key") == key:
            return seen["job_id"]
        if seen.get("client_id") == job.client_id and \
                SequenceMatcher(None, seen.get("title", "").lower(), job.title.lower()).ratio() > 0.9:
            return seen["job_id"]
    return None


async def scout_search(port: MarketplacePort, saved_searches: list[dict[str, Any]], since: str | None,
                       known_ids: set[str], recent: list[dict[str, Any]]) -> tuple[list[Job], list[tuple[Job, str]]]:
    """Run every saved search; return (new jobs to analyse, duplicates with the id they repeat)."""
    new: list[Job] = []
    duplicates: list[tuple[Job, str]] = []
    seen_now: list[dict[str, Any]] = list(recent)
    for search in saved_searches:
        jobs = await port.search_jobs(query=search.get("query", ""), skills=search.get("skills", []),
                                      category=search.get("category", ""), since=since,
                                      limit=int(search.get("limit", 30)))
        for job in jobs:
            if job.job_id in known_ids:
                continue
            known_ids.add(job.job_id)
            original = is_near_duplicate(job, seen_now)
            if original:
                duplicates.append((job, original))
            else:
                new.append(job)
            seen_now.append({"job_id": job.job_id, "content_key": content_key(job), "client_id": job.client_id,
                             "title": job.title})
    return new, duplicates


@node("scout")
async def intake(state: dict, config: RunnableConfig) -> dict:
    """Make sure the thread has the full job (the worker may queue only an id) and stop duplicates early."""
    job: Job = state["job"]
    if not job.description:
        port = MarketplacePort(tools_for("scout", config))
        job = await port.get_job(job.job_id)
    duplicate_of = ctx(config).get("duplicate_of")
    if duplicate_of:
        return {"job": job, "status": "skipped", "status_reason": f"duplicate of {duplicate_of}"}
    return {"job": job, "status": "running"}
