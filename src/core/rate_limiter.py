"""
TokenBucket — Thread-safe RPM enforcement via token-bucket algorithm.
Ported from the CLI agent with no UI dependencies.
"""

import threading
import time
from collections import deque
from typing import Optional


class TokenBucket:
    """
    Thread-safe token-bucket rate limiter.

    Parameters
    ----------
    rpm : float
        Requests-per-minute ceiling (before safety margin).
    burst : int
        Maximum tokens that can accumulate (burst capacity).
    min_gap : float
        Minimum seconds between consecutive requests.
    safety_margin : float
        Multiplier applied to ceiling_rpm to get effective rpm
        (e.g. 0.8 means we only use 80% of the advertised RPM).
    """

    def __init__(
        self,
        rpm: float = 20.0,
        burst: int = 1,
        min_gap: float = 1.0,
        safety_margin: float = 0.8,
    ):
        self.ceiling_rpm: float = max(1.0, rpm)
        self.rpm: float = self.ceiling_rpm * safety_margin
        self.burst: int = burst
        self.base_min_gap: float = min_gap
        self.tokens: float = float(burst)
        self.last_update: float = time.monotonic()
        self.last_request_time: float = 0.0
        self.lock: threading.Lock = threading.Lock()
        self.history: deque[float] = deque()

    # ------------------------------------------------------------------
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(
            self.burst, self.tokens + elapsed * (self.rpm / 60.0)
        )
        self.last_update = now

    def _prune(self) -> None:
        cutoff = time.monotonic() - 60.0
        while self.history and self.history[0] < cutoff:
            self.history.popleft()

    def _wait_time(self) -> float:
        self._refill()
        self._prune()
        waits: list[float] = []
        if self.tokens < 1.0:
            waits.append((1.0 - self.tokens) / (self.rpm / 60.0))
        if len(self.history) >= max(1, int(self.rpm)):
            if self.history:
                waits.append(60.0 - (time.monotonic() - self.history[0]) + 0.5)
        since_last = time.monotonic() - self.last_request_time
        if since_last < self.base_min_gap:
            waits.append(self.base_min_gap - since_last)
        return max(waits) if waits else 0.0

    # ------------------------------------------------------------------
    def reserve(self, timeout: float = 60.0) -> bool:
        """Block until a token is available or *timeout* expires."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                wait = self._wait_time()
                if wait <= 0.01:
                    self.tokens -= 1.0
                    self.last_request_time = time.monotonic()
                    return True
            time.sleep(wait)
        return False

    def commit(self) -> None:
        """Record a successful request in the rolling history."""
        with self.lock:
            self.history.append(time.monotonic())


class TokenMeter:
    """Accumulates prompt/completion token counts thread-safely."""

    def __init__(self) -> None:
        self.total_prompt: int = 0
        self.total_completion: int = 0
        self.lock: threading.Lock = threading.Lock()

    def record(self, prompt_tokens: int, completion_tokens: int) -> None:
        with self.lock:
            self.total_prompt += max(0, prompt_tokens)
            self.total_completion += max(0, completion_tokens)
