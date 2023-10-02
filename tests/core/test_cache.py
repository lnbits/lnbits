import asyncio

import pytest

from lnbits.utils.cache import Cache
from tests.conftest import pytest_asyncio

key = "foo"
value = "bar"


@pytest_asyncio.fixture
async def cache():
    cache = Cache(interval=0.1)

    task = asyncio.create_task(cache.invalidate_forever())
    yield cache
    task.cancel()


@pytest.mark.asyncio
async def test_cache_get_set(cache):
    cache.set(key, value)
    assert cache.get(key) == value
    assert cache.get(key, default="default") == value
    assert cache.get("i-dont-exist", default="default") == "default"


@pytest.mark.asyncio
async def test_cache_expiry(cache):
    # gets expired by `get` call
    cache.set(key, value, expiry=0.01)
    await asyncio.sleep(0.02)
    assert not cache.get(key)

    # gets expired by invalidation task
    cache.set(key, value, expiry=0.1)
    await asyncio.sleep(0.2)
    assert key not in cache._values
    assert not cache.get(key)


@pytest.mark.asyncio
async def test_cache_pop(cache):
    cache.set(key, value)
    assert cache.pop(key) == value
    assert not cache.get(key)
    assert cache.pop(key, default="a") == "a"


@pytest.mark.asyncio
async def test_cache_coro(cache):
    called = 0

    async def test():
        nonlocal called
        called += 1
        return called

    await cache.save_result(test, key="test")
    result = await cache.save_result(test, key="test")
    assert result == called == 1
