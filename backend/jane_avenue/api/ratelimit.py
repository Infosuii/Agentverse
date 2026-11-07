"""In-memory token bucket for `POST /api/analyses` (agent-1 brief, M2 input limits). Owner: agent-1.

Each client (by host) holds up to `capacity` tokens, refilled continuously at `per_minute` a minute. One analysis
costs one token. Enabled only in live mode, where each analysis spends Gemini quota.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable


class TokenBucket:
    def __init__(self, per_minute: float = 6, capacity: float | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.rate = per_minute / 60.0
        self.capacity = capacity if capacity is not None else per_minute
        self._clock = clock
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str) -> tuple[bool, int]:
        """Spend one token for `key`. Returns (allowed, seconds until the next token if not allowed)."""
        now = self._clock()
        with self._lock:
            tokens, last = self._buckets.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens >= 1:
                self._buckets[key] = (tokens - 1, now)
                return True, 0
            self._buckets[key] = (tokens, now)
            return False, max(1, math.ceil((1 - tokens) / self.rate))
