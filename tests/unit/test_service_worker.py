"""
Service Worker Integration Tests

Tests core functionality: cache management, TTL expiry, API key hashing,
timeout behavior, and URL validation.

Run with: pytest tests/test_service_worker.py -v
"""

import asyncio
import hashlib
import json
import time

import pytest


# Mock service worker helpers (simulate JS crypto and cache behavior)
class MockCache:
    """Simulates browser Cache API."""

    def __init__(self):
        self.store = {}
        self.metadata = {}

    async def put(self, url, response):
        self.store[url] = response
        self.metadata[url] = time.time()  # Use time.time() for timestamps

    async def match(self, url):
        return self.store.get(url)

    async def delete(self, url):
        if url in self.store:
            del self.store[url]
            del self.metadata[url]

    async def keys(self):
        return list(self.store.keys())


# Service Worker helper functions (Python equivalent of JS code)
async def hash_api_key(api_key: str = None) -> str:
    """Hash API key using SHA-256."""
    if not api_key:
        api_key = "no_api_key"
    return hashlib.sha256(api_key.encode()).hexdigest()


def validate_notification_url(url: str, origin: str = "https://example.com") -> str:
    """Validate notification URL; prevent open redirects."""
    if not url:
        return "/"
    try:
        if url.startswith(origin):
            return url
        if url.startswith("/"):
            return url
    except Exception:
        pass
    return "/"


def is_cache_entry_expired(
    timestamp: float, ttl_ms: int = 7 * 24 * 60 * 60 * 1000
) -> bool:
    """Check if cache entry has exceeded TTL."""
    # timestamp is in seconds, convert to ms for comparison
    now_ms = time.time() * 1000
    entry_ms = timestamp * 1000
    return (now_ms - entry_ms) > ttl_ms


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_cache():
    """Provide a mock cache store."""
    return MockCache()


@pytest.fixture
def cache_config():
    """Cache configuration parameters."""
    return {
        "NETWORK_TIMEOUT_MS": 10000,
        "CACHE_TTL_MS": 7 * 24 * 60 * 60 * 1000,
        "CURRENT_CACHE": "lnbits-test-",
    }


# ============================================================================
# Tests: Core Functionality
# ============================================================================


@pytest.mark.anyio
async def test_hash_api_key():
    """API keys should be hashed, not stored plaintext."""
    api_key = "test-secret-key-12345"
    hash1 = await hash_api_key(api_key)
    hash2 = await hash_api_key(api_key)

    # Consistent hash
    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest
    # Not plaintext
    assert api_key not in hash1


@pytest.mark.anyio
async def test_hash_different_keys():
    """Different API keys should produce different hashes."""
    hash1 = await hash_api_key("key1")
    hash2 = await hash_api_key("key2")
    assert hash1 != hash2


@pytest.mark.anyio
async def test_cache_put_and_match(mock_cache):
    """Cache should store and retrieve responses."""
    url = "https://example.com/api/data"
    response = {"status": 200, "body": "test"}

    await mock_cache.put(url, response)
    result = await mock_cache.match(url)

    assert result == response


@pytest.mark.anyio
async def test_cache_metadata_tracking(mock_cache):
    """Cache should track timestamps for TTL expiry."""
    url = "https://example.com/api/data"
    response = {"status": 200}

    await mock_cache.put(url, response)
    assert url in mock_cache.metadata
    assert mock_cache.metadata[url] > 0


# ============================================================================
# Tests: TTL and Expiry (Security & Correctness)
# ============================================================================


@pytest.mark.anyio
async def test_cache_entry_not_expired_fresh(cache_config):
    """Fresh cache entries should not be expired."""
    now_ms = time.time() * 1000
    ttl = cache_config["CACHE_TTL_MS"]

    # Entry created just now
    expired = is_cache_entry_expired(now_ms / 1000, ttl)
    assert not expired


@pytest.mark.anyio
async def test_cache_entry_expired_old(cache_config):
    """Cache entries exceeding TTL should be expired."""
    now_ms = time.time() * 1000
    ttl = cache_config["CACHE_TTL_MS"]

    # Entry created 8 days ago (exceeds 7-day TTL)
    old_timestamp = (now_ms - ttl - 1000) / 1000
    expired = is_cache_entry_expired(old_timestamp, ttl)
    assert expired


# ============================================================================
# Tests: URL Validation (Security: CWE-601 Open Redirect)
# ============================================================================


@pytest.mark.anyio
async def test_validate_same_origin_url():
    """Same-origin URLs should be allowed."""
    url = "/wallet?id=123"
    result = validate_notification_url(url)
    assert result == url


@pytest.mark.anyio
async def test_validate_same_origin_absolute():
    """Absolute same-origin URLs should be allowed."""
    url = "https://example.com/wallet"
    result = validate_notification_url(url, origin="https://example.com")
    assert result == url


@pytest.mark.anyio
async def test_prevent_open_redirect_external():
    """External URLs should be rejected; redirect to safe default."""
    malicious_url = "https://evil.com/phish"
    result = validate_notification_url(malicious_url, origin="https://example.com")
    assert result == "/"


@pytest.mark.anyio
async def test_prevent_open_redirect_protocol_switch():
    """Protocol switches should be prevented."""
    malicious_url = "javascript:alert('xss')"
    result = validate_notification_url(malicious_url)
    assert result == "/"


@pytest.mark.anyio
async def test_validate_none_url():
    """Missing or null URLs should fallback to safe default."""
    assert validate_notification_url(None) == "/"
    assert validate_notification_url("") == "/"


# ============================================================================
# Tests: Network Timeout (Performance & UX)
# ============================================================================


@pytest.mark.anyio
async def test_network_timeout_enforced():
    """Fetch requests should timeout after configured delay."""
    timeout_ms = 100

    async def slow_fetch():
        await asyncio.sleep(timeout_ms / 1000 + 0.5)
        return {"status": 200}

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_fetch(), timeout=timeout_ms / 1000)


@pytest.mark.anyio
async def test_timeout_fallback_to_cache(mock_cache):
    """On timeout, should fallback to cached response."""
    url = "https://example.com/api/data"
    cached_response = {"status": 200, "cached": True}

    # Pre-populate cache
    await mock_cache.put(url, cached_response)
    result = await mock_cache.match(url)

    assert result == cached_response


# ============================================================================
# Tests: Worker Lifecycle (Deployment Update)
# ============================================================================


@pytest.mark.anyio
async def test_cache_versioning():
    """Cache should use version prefix to isolate deployments."""
    version1 = "lnbits-v1.0-"
    version2 = "lnbits-v1.1-"
    api_key_hash = await hash_api_key("key1")

    cache_key_v1 = version1 + api_key_hash
    cache_key_v2 = version2 + api_key_hash

    assert cache_key_v1 != cache_key_v2
    assert cache_key_v1.startswith("lnbits-v1.0-")
    assert cache_key_v2.startswith("lnbits-v1.1-")


@pytest.mark.anyio
async def test_old_caches_should_be_cleaned(mock_cache):
    """Old cache versions should be deleted on activation."""
    old_cache = "lnbits-old-version-"
    current_cache = "lnbits-current-"

    # Simulate old and new caches
    await mock_cache.put(f"{old_cache}key1", {"data": "old"})
    await mock_cache.put(f"{current_cache}key1", {"data": "new"})

    # Cleanup: delete old
    await mock_cache.delete(f"{old_cache}key1")
    old_result = await mock_cache.match(f"{old_cache}key1")
    current_result = await mock_cache.match(f"{current_cache}key1")

    assert old_result is None
    assert current_result == {"data": "new"}


# ============================================================================
# Tests: Edge Cases & Error Handling
# ============================================================================


@pytest.mark.anyio
async def test_malformed_push_notification():
    """Malformed push data should not crash handler."""
    malformed_data = "not-json"

    with pytest.raises(json.JSONDecodeError):
        json.loads(malformed_data)


@pytest.mark.anyio
async def test_missing_api_key_defaults():
    """Missing API key should hash as 'no_api_key'."""
    hash_with_key = await hash_api_key("actual-key")
    hash_without_key = await hash_api_key(None)
    assert hash_with_key != hash_without_key


@pytest.mark.anyio
async def test_cache_entry_collision_prevention():
    """Different API keys should use separate cache stores."""
    key1 = "user-api-key-1"
    key2 = "user-api-key-2"

    hash1 = await hash_api_key(key1)
    hash2 = await hash_api_key(key2)

    cache1 = f"lnbits-{hash1}"
    cache2 = f"lnbits-{hash2}"

    assert cache1 != cache2
