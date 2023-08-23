from __future__ import annotations

import asyncio
from time import time
from typing import Any, NamedTuple, Optional

from loguru import logger


class Cached(NamedTuple):
    value: Any
    expiry: float


class Cache:
    """
    Small caching utility providing simple get/set interface (very much like redis)
    """

    def __init__(self):
        self._values: dict[Any, Cached] = {}

    def get(self, key: str, default=None) -> Optional[Any]:
        cached = self._values.get(key)
        if cached is not None:
            if cached.expiry > time():
                return cached.value
            else:
                self._values.pop(key)
        return default

    def set(self, key: str, value: Any, expiry: float = 10):
        self._values[key] = Cached(value, time() + expiry)

    def pop(self, key: str, default=None) -> Optional[Any]:
        cached = self._values.pop(key, None)
        if cached and cached.expiry > time():
            return cached.value
        return default

    async def save_result(self, coro, key: str, expiry: float = 10):
        """
        If `key` exists, return its value, otherwise call coro and cache its result
        """
        cached = self.get(key)
        if cached:
            return cached
        else:
            value = await coro()
            self.set(key, value, expiry=expiry)
            return value

    async def invalidate_forever(self, interval: float = 10):
        while True:
            try:
                await asyncio.sleep(interval)
                ts = time()
                expired = [k for k, v in self._values.items() if v.expiry < ts]
                for k in expired:
                    self._values.pop(k)
            except Exception:
                logger.error("Error invalidating cache")


cache = Cache()
