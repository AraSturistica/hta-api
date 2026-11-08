import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key_id: str, limit: int, window: float = 3600.0) -> float | None:
        """Devuelve None si permitido, o segundos de espera."""
        now = time.monotonic()
        q = self._hits[key_id]
        while q and q[0] <= now - window:
            q.popleft()
        if len(q) >= limit:
            return max(1.0, q[0] + window - now)
        q.append(now)
        return None
