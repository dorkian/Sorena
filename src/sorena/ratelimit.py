import time
from collections import deque


class RateLimiter:
    """Sliding 60s window per model. allow() before calling, record() after a successful call."""

    def __init__(self, limits_rpm: dict[str, int]):
        self._limits = limits_rpm
        self._calls: dict[str, deque] = {model: deque() for model in limits_rpm}

    def allow(self, model: str) -> bool:
        limit = self._limits.get(model)
        if limit is None:
            return True
        now = time.monotonic()
        calls = self._calls[model]
        while calls and now - calls[0] > 60:
            calls.popleft()
        return len(calls) < limit

    def record(self, model: str) -> None:
        self._calls.setdefault(model, deque()).append(time.monotonic())
