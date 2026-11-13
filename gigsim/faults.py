"""Per-token rate limit and seeded fault injection."""
from __future__ import annotations

import math
import random
import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    """Sliding window of 60 real seconds per token."""

    def __init__(self, limit_per_minute: int):
        self.limit = limit_per_minute
        self.calls: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, token: str) -> int | None:
        """None if the call is allowed, else the number of seconds to wait."""
        now = time.monotonic()
        with self.lock:
            window = self.calls[token]
            while window and now - window[0] >= 60:
                window.popleft()
            if len(window) >= self.limit:
                return max(1, math.ceil(60 - (now - window[0])))
            window.append(now)
            return None


class FaultInjector:
    """Draws from a seeded RNG, so a run with the same seed and the same call order fails at the same calls.

    A fault is "before" (nothing happened) or, for writes that carry an Idempotency-Key, sometimes "after"
    (the write was done but the answer is lost), which is the case idempotency keys exist for.
    """

    def __init__(self, error_rate: float, seed: int):
        self.error_rate = error_rate
        self.rng = random.Random(seed)
        self.lock = threading.Lock()

    def draw(self, is_write_with_key: bool) -> str | None:
        with self.lock:
            hit = self.rng.random() < self.error_rate
            after = self.rng.random() < 0.4
        if not hit:
            return None
        return "after" if (after and is_write_with_key) else "before"
