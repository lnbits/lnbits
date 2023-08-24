import asyncio

import pytest

from lnbits.cache import cache

key = "foo"
value = "bar"


@pytest.mark.asyncio
async def test_cache_get_set():
    cache.set(key, value)
    assert cache.get(key) == value
    assert cache.get(key, default="default") == value
    assert cache.get("i-dont-exist", default="default") == "default"


@pytest.mark.asyncio
async def test_cache_expiry():
    cache.set(key, value, expiry=0.1)
    await asyncio.sleep(0.2)
    assert not cache.get(key)


@pytest.mark.asyncio
async def test_cache_pop():
    cache.set(key, value)
    assert cache.pop(key) == value
    assert not cache.get(key)
    assert cache.pop(key, default="a") == "a"


@pytest.mark.asyncio
async def test_cache_coro():
    called = 0

    async def test():
        nonlocal called
        called += 1
        return called

    await cache.save_result(test, key="test")
    result = await cache.save_result(test, key="test")
    assert result == called == 1
