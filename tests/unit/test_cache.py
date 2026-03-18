import asyncio
from time import time

import pytest
from pytest_mock.plugin import MockerFixture

from lnbits.settings import Settings
from lnbits.utils.cache import Cache, Cached

key = "foo"
value = "bar"


@pytest.fixture
async def cache():
    cache = Cache(interval=0.1)

    task = asyncio.create_task(cache.invalidate_forever())
    yield cache
    task.cancel()


@pytest.mark.anyio
async def test_cache_get_set(cache):
    cache.set(key, value)
    assert cache.get(key) == value
    assert cache.get(key, default="default") == value
    assert cache.get("i-dont-exist", default="default") == "default"


@pytest.mark.anyio
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


def test_cached_older_than():
    cached = Cached(value="value", expiry=time() - 5)

    assert cached.older_than(1) is True
    assert cached.older_than(10) is False


@pytest.mark.anyio
async def test_cache_value_returns_cached_metadata(cache):
    cache.set(key, value, expiry=1)

    cached = cache.value(key)

    assert cached is not None
    assert cached.value == value
    assert cached.expiry > time()


@pytest.mark.anyio
async def test_cache_pop_expired_returns_default(cache):
    cache.set(key, value, expiry=0.01)
    await asyncio.sleep(0.02)

    assert cache.pop(key, default="fallback") == "fallback"


@pytest.mark.anyio
async def test_invalidate_forever_logs_and_recovers_from_errors(
    settings: Settings, mocker: MockerFixture
):
    test_cache = Cache(interval=0)
    logger_error = mocker.patch("lnbits.utils.cache.logger.error")
    original_running = settings.lnbits_running
    calls = 0

    async def fake_sleep(_interval):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        settings.lnbits_running = False

    try:
        settings.lnbits_running = True
        mocker.patch("lnbits.utils.cache.asyncio.sleep", side_effect=fake_sleep)
        await test_cache.invalidate_forever()
    finally:
        settings.lnbits_running = original_running

    logger_error.assert_called_once_with("Error invalidating cache")
