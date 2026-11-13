"""Hands long work to the worker (Arq on Redis). Without Redis (local dev, tests) it runs as a background task.

Web requests never run a graph themselves; they enqueue and return, and the UI streams progress.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

_pool = None
_background: set[asyncio.Task] = set()


async def enqueue(function: str, *args: Any, job_id: str | None = None) -> bool:
    global _pool
    if os.environ.get("REDIS_URL"):
        from arq import create_pool
        from arq.connections import RedisSettings

        if _pool is None:
            _pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
        job = await _pool.enqueue_job(function, *args, _job_id=job_id)
        return job is not None  # None: the same job id is already queued (idempotent enqueue)
    from worker import tasks

    task = asyncio.create_task(getattr(tasks, function)({}, *args))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return True
