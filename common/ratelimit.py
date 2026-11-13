"""Per-user sliding-window rate limiter (Redis when REDIS_URL is set, in-process otherwise)."""
from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, per_minute: int, name: str = "rl"):
        self.per_minute = per_minute
        self.name = name
        self._local: dict[str, deque[float]] = defaultdict(deque)
        self._redis = None
        if os.environ.get("REDIS_URL"):
            import redis.asyncio as redis

            self._redis = redis.from_url(os.environ["REDIS_URL"])

    async def wait_time(self, user_id: str) -> float:
        """Seconds to wait before this user's next call is allowed (0 = go now). Records the call when allowed."""
        now = time.time()
        if self._redis is not None:
            try:
                key = f"{self.name}:{user_id}"
                pipe = self._redis.pipeline()
                pipe.zremrangebyscore(key, 0, now - 60)
                pipe.zrange(key, 0, 0, withscores=True)
                pipe.zcard(key)
                _, oldest, count = await pipe.execute()
                if count >= self.per_minute:
                    return max(0.05, 60 - (now - oldest[0][1]))
                await self._redis.zadd(key, {f"{now}": now})
                await self._redis.expire(key, 61)
                return 0.0
            except Exception:
                pass  # fall back to the local window if Redis is unreachable
        window = self._local[user_id]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.per_minute:
            return max(0.05, 60 - (now - window[0]))
        window.append(now)
        return 0.0

    async def acquire(self, user_id: str, max_wait: float = 30.0) -> None:
        """Wait politely (up to `max_wait` seconds) until the call is allowed."""
        waited = 0.0
        while True:
            delay = await self.wait_time(user_id)
            if delay == 0:
                return
            if waited + delay > max_wait:
                raise TimeoutError(f"rate limit: retry in {delay:.0f}s")
            await asyncio.sleep(delay)
            waited += delay
