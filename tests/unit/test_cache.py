import asyncio

import pytest

from lnbits.task_manager import task_manager
from lnbits.utils.cache import Cache

key = "foo"
value = "bar"


@pytest.fixture
async def cache():
    cache = Cache()
    task = task_manager.create_permanent_task(cache.invalidate_cache, interval=1)
    yield cache
    task_manager.cancel_task(task)


@pytest.mark.anyio
async def test_cache_get_set(cache):
    cache.set(key, value)
    assert cache.get(key) == value
    assert cache.get(key, default="default") == value
    assert cache.get("i-dont-exist", default="default") == "default"


@pytest.mark.anyio
async def test_cache_expiry(cache):
    # gets expired by `get` call
    cache.set(key, value, expiry=1)
    await asyncio.sleep(2)
    assert not cache.get(key)

    # gets expired by invalidation task
    cache.set(key, value, expiry=1)
    await asyncio.sleep(2)
    assert key not in cache._values
    assert not cache.get(key)


@pytest.mark.anyio
async def test_cache_pop(cache):
    cache.set(key, value)
    assert cache.pop(key) == value
    assert not cache.get(key)
    assert cache.pop(key, default="a") == "a"


@pytest.mark.anyio
async def test_cache_coro(cache):
    called = 0

    async def test():
        nonlocal called
        called += 1
        return called

    await cache.save_result(test, key="test")
    result = await cache.save_result(test, key="test")
    assert result == called == 1
