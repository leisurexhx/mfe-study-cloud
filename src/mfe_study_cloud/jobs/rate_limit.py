"""Process-wide provider request pacing shared by worker threads."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class ProviderRateLimiter:
    """A thread-safe rolling-window request limiter.

    This deliberately controls requests within one worker process. Operators running
    multiple worker replicas must divide the configured account allowance between them.
    """

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        self._limit = requests_per_minute
        self._clock = clock
        self._sleep = sleeper
        self._requests: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            wait_seconds = 0.0
            with self._lock:
                now = self._clock()
                cutoff = now - 60.0
                while self._requests and self._requests[0] <= cutoff:
                    self._requests.popleft()
                if len(self._requests) < self._limit:
                    self._requests.append(now)
                    return
                wait_seconds = max(0.001, self._requests[0] + 60.0 - now)
            self._sleep(wait_seconds)
