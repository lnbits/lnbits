from __future__ import annotations

import asyncio
from time import time
from typing import Any, NamedTuple, Optional

from loguru import logger


class Cached(NamedTuple):
    value: Any
    stale: float
    expiry: float


def _add_prefix(key: str, prefix: str):
    return prefix + ":" + key if prefix else key


class Cache:
    def __init__(self):
        self._values: dict[Any, Cached] = {}

    def get(self, key: str, prefix: str = "") -> Optional[Any]:
        cached = self._values.get(_add_prefix(key, prefix))
        if cached is not None:
            if cached.expiry > time():
                return cached.value
            else:
                self.pop(key, prefix)
        return None

    def set(self, key: str, value: Any, expiry: float = 10, prefix: str = ""):
        ts = time()
        self._values[_add_prefix(key, prefix)] = Cached(
            value, ts + expiry / 2, ts + expiry
        )

    def pop(self, key: str, prefix: str = "") -> Optional[Any]:
        return self._values.pop(_add_prefix(key, prefix), None)

    async def get_and_revalidate(
        self, coro, key: str, expiry: float = 20, prefix: str = ""
    ):
        """
        Stale while revalidate cache
        Gets a result from the cache if it exists, otherwise run the coroutine and cache the result
        """
        cached = self._values.get(key)
        if cached:
            ts = time()
            if ts < cached.expiry:
                if ts > cached.stale:
                    asyncio.create_task(coro()).add_done_callback(
                        lambda fut: self.set(key, fut.result(), expiry, prefix)
                    )
                return cached.value
        value = await coro()
        self.set(key, value, expiry, prefix)
        return value

    async def invalidate_forever(self):
        while True:
            try:
                await asyncio.sleep(10)
                ts = time()
                self._values = {k: v for k, v in self._values.items() if v.expiry > ts}
            except Exception:
                logger.error("Error invalidating cache")


cache = Cache()
