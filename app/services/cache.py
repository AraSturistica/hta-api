import asyncio
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable


class HTACache:
    """TTL + single-flight: una sola ejecución por clave concurrente."""

    def __init__(self, ttl: int, max_entries: int = 200):
        self.ttl, self.max_entries = ttl, max_entries
        self._data: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._locks: dict[str, asyncio.Lock] = {}

    def _get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if item and item[0] > time.monotonic():
            self._data.move_to_end(key)
            return item[1]
        self._data.pop(key, None)
        return None

    async def get_or_fetch(self, key: str, fetch: Callable[[], Awaitable[Any]]) -> tuple[Any, bool]:
        hit = self._get(key)
        if hit is not None:
            return hit, True
        lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            hit = self._get(key)
            if hit is not None:
                return hit, True
            value = await fetch()
            self._data[key] = (time.monotonic() + self.ttl, value)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)
            return value, False
        
    def invalidate(self, prefix: str = "") -> None:
        for k in [k for k in self._data if k.startswith(prefix)]:
            del self._data[k]
