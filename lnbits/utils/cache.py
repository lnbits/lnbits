from __future__ import annotations

import asyncio
from time import time
from typing import Any, NamedTuple

from loguru import logger

from lnbits.settings import settings


class Cached(NamedTuple):
    value: Any
    expiry: float

    def older_than(self, seconds: float) -> bool:
        return time() - self.expiry > seconds


class Cache:
    """
    Small caching utility providing simple get/set interface (very much like redis)
    """

    def __init__(self, interval: float = 10) -> None:
        self.interval = interval
        self._values: dict[Any, Cached] = {}
        self._refreshing: set[str] = set()
        self._tasks: set[asyncio.Task] = set()

    def value(self, key: str) -> Cached | None:
        return self._values.get(key)

    def get(self, key: str, default=None) -> Any | None:
        cached = self._values.get(key)
        if cached is not None:
            if cached.expiry > time():
                return cached.value
            else:
                self._values.pop(key)
        return default

    def set(self, key: str, value: Any, expiry: float = 10):
        self._values[key] = Cached(value, time() + expiry)

    def pop(self, key: str, default=None) -> Any | None:
        cached = self._values.pop(key, None)
        if cached and cached.expiry > time():
            return cached.value
        return default

    async def save_result(self, coro, key: str, expiry: float = 10):
        """
        Stale-while-revalidate: return stale value immediately and refresh in
        the background. Only blocks on a true cold start (no prior value).
        """
        cached = self._values.get(key)
        if cached is not None:
            if cached.expiry > time():
                return cached.value
            # stale: serve old value and refresh in background (one task at a time)
            if key not in self._refreshing:
                self._refreshing.add(key)
                # extend expiry now to prevent a stampede of background tasks
                self._values[key] = Cached(cached.value, time() + expiry)
                task = asyncio.create_task(self._refresh(coro, key, expiry))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            return cached.value
        # cold start: must wait for the first value
        value = await coro()
        self.set(key, value, expiry=expiry)
        return value

    async def _refresh(self, coro, key: str, expiry: float):
        try:
            value = await coro()
            self.set(key, value, expiry=expiry)
        except Exception:
            logger.error(f"Error refreshing cache key {key}")
        finally:
            self._refreshing.discard(key)

    async def invalidate_forever(self):
        while settings.lnbits_running:
            try:
                await asyncio.sleep(self.interval)
                ts = time()
                expired = [k for k, v in self._values.items() if v.expiry < ts]
                for k in expired:
                    self._values.pop(k)
            except Exception:
                logger.error("Error invalidating cache")


cache = Cache()
