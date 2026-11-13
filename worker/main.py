"""Arq worker settings: queued tasks plus cron schedules for scouting, event tracking and degraded-mode recovery.

Run: arq worker.main.WorkerSettings
"""
from __future__ import annotations

from arq import cron
from arq.connections import RedisSettings

from common.tracing import setup_tracing
from worker import tasks


async def startup(ctx: dict) -> None:
    setup_tracing("worker")


class WorkerSettings:
    functions = [tasks.analyze_job, tasks.resume_thread, tasks.conversation, tasks.scout_user, tasks.track_events]
    cron_jobs = [
        cron(tasks.scout_all, minute={0, 30}, run_at_startup=False),   # each saved search has its own interval
        cron(tasks.track_all, minute=set(range(0, 60, 5))),
        cron(tasks.requeue_degraded, minute=set(range(2, 60, 5))),
    ]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(tasks.worker_redis_url())
    max_jobs = 4
    job_timeout = 900
    keep_result = 3600
