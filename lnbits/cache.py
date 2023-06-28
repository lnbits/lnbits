from __future__ import annotations

import asyncio
from time import time
from typing import Any, NamedTuple, Optional

from loguru import logger


class Cached(NamedTuple):
    value: Any
    expiry: float


def _add_prefix(key: str, prefix: str):
    return prefix + ":" + key if prefix else key


class Cache:
    """
    Small caching utility providing simple get/set interface (very much like redis)
    """

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
        self._values[_add_prefix(key, prefix)] = Cached(value, time() + expiry)

    def pop(self, key: str, prefix: str = "", default=None) -> Optional[Any]:
        cached = self._values.pop(_add_prefix(key, prefix), None)
        if cached:
            return cached.value
        return default

    async def save_result(self, coro, key: str, expiry: float = 10, prefix: str = ""):
        """
        Call the coroutine and cache its result
        """
        cached = self.get(key, prefix)
        if cached:
            return cached
        else:
            value = await coro()
            self.set(key, value, expiry=expiry, prefix=prefix)
            return value

    async def invalidate_forever(self, interval: float = 1):
        while True:
            try:
                await asyncio.sleep(interval)
                ts = time()
                self._values = {k: v for k, v in self._values.items() if v.expiry > ts}
            except Exception:
                logger.error("Error invalidating cache")


cache = Cache()
