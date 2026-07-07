import asyncio
import os
import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from lnbits.settings import settings
from lnbits.wallets import get_funding_source, set_funding_source
from lnbits.wallets.base import PaymentStatus
from lnbits.wallets.blink import BlinkWallet, TokenBucket

settings.lnbits_backend_wallet_class = "BlinkWallet"
settings.blink_token = "mock"
settings.blink_api_endpoint = "https://api.blink.sv/graphql"

# Check if BLINK_TOKEN environment variable is set
use_real_api = os.environ.get("BLINK_TOKEN") is not None
logger.info(f"use_real_api: {use_real_api}")

if use_real_api:
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": os.environ.get("BLINK_TOKEN"),
    }
    settings.blink_token = os.environ.get("BLINK_TOKEN")


logger.info(
    f"settings.lnbits_backend_wallet_class: {settings.lnbits_backend_wallet_class}"
)
logger.info(f"settings.blink_api_endpoint: {settings.blink_api_endpoint}")
logger.info(f"settings.blink_token: {settings.blink_token}")

set_funding_source()
funding_source = cast(BlinkWallet, get_funding_source())
assert isinstance(funding_source, BlinkWallet)


@pytest.fixture(scope="session")
def payhash():
    payment_hash = "14d7899c3456bcd78f7f18a70d782b8eadb2de974e80dc5120e133032423dcda"
    return payment_hash


@pytest.fixture(scope="session")
def outbound_bolt11():
    bolt11 = "lnbc1u1pjl0uhypp5yxvdqq923atm9ywkpgtu3yxv9w2n44ensrkwfyagvmzqhml2x9gqdpv2phhwetjv4jzqcneypqyc6t8dp6xu6twva2xjuzzda6qcqzzsxqrrsssp5h3qlnnlfqekquacwwj9yu7fhujyzxhzqegpxenscw45pgv6xakfq9qyyssqqjruygw0jrcg3365jksxn6yhsxx7c5pdjrjdlyvuhs7xh8r409h4e3kucc54kgh34pscaq3mg7hn55l8a0qszgzex80amwrp4gkdgqcpkse88y"  # noqa: E501
    return bolt11


# ── Integration tests (require BLINK_TOKEN) ─────────────────────────


@pytest.mark.anyio
async def test_environment_variables():
    if use_real_api:
        assert "X-API-KEY" in headers, "X-API-KEY is not present in headers"
        assert isinstance(headers["X-API-KEY"], str), "X-API-KEY is not a string"
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_get_wallet_id():
    if use_real_api:
        wallet_id = await funding_source._init_wallet_id()
        logger.info(f"test_get_wallet_id: {wallet_id}")
        assert wallet_id
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_status():
    if use_real_api:
        status = await funding_source.status()
        logger.info(f"test_status: {status}")
        assert status
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_create_invoice():
    if use_real_api:
        invoice_response = await funding_source.create_invoice(amount=1000, memo="test")
        assert invoice_response.ok is True
        assert invoice_response.payment_request
        assert invoice_response.checking_id
        logger.info(f"test_create_invoice: ok: {invoice_response.ok}")
        logger.info(
            f"test_create_invoice: payment_request: {invoice_response.payment_request}"
        )

        payment_status = await funding_source.get_invoice_status(
            invoice_response.checking_id
        )
        assert payment_status.paid is None  # still pending

        logger.info(
            f"test_create_invoice: PaymentStatus is Still Pending: {payment_status.paid is None}"  # noqa: E501
        )
        logger.info(
            f"test_create_invoice: PaymentStatusfee_msat: {payment_status.fee_msat}"
        )
        logger.info(
            f"test_create_invoice: PaymentStatus preimage: {payment_status.preimage}"
        )

    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_pay_invoice_self_payment():
    if use_real_api:
        invoice_response = await funding_source.create_invoice(amount=100, memo="test")
        assert invoice_response.ok is True
        bolt11 = invoice_response.payment_request
        assert bolt11 is not None
        payment_response = await funding_source.pay_invoice(bolt11, fee_limit_msat=100)
        assert payment_response.ok is False  # can't pay self
        assert payment_response.error_message

    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_outbound_invoice_payment(outbound_bolt11):
    if use_real_api:
        payment_response = await funding_source.pay_invoice(
            outbound_bolt11, fee_limit_msat=100
        )
        assert payment_response.ok is True
        assert payment_response.checking_id
        logger.info(f"test_outbound_invoice_payment: ok: {payment_response.ok}")
        logger.info(
            f"test_outbound_invoice_payment: checking_id: {payment_response.checking_id}"  # noqa: E501
        )
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


@pytest.mark.anyio
async def test_get_payment_status(payhash):
    if use_real_api:
        payment_status = await funding_source.get_payment_status(payhash)
        assert payment_status.paid
        logger.info(f"test_get_payment_status: payment_status: {payment_status.paid}")
    else:
        assert True, "BLINK_TOKEN is not set. Skipping test using mock api"


# ── Unit tests for internal components (no API needed) ──────────────


class TestTokenBucket:
    @pytest.mark.anyio
    async def test_consume_allows_within_rate(self):
        bucket = TokenBucket(10, 60)
        for _ in range(10):
            await bucket.consume()
        # All consumed without blocking - tokens should be 0
        assert bucket.tokens == 0

    @pytest.mark.anyio
    async def test_consume_blocks_when_exhausted(self):
        bucket = TokenBucket(2, 10)
        await bucket.consume()
        await bucket.consume()
        assert bucket.tokens == 0
        # Next consume should wait - time it
        start = time.monotonic()
        await bucket.consume()
        elapsed = time.monotonic() - start
        assert elapsed >= 4.5  # ~5s per token at 2/10s rate

    @pytest.mark.anyio
    async def test_refills_over_time(self):
        bucket = TokenBucket(60, 60)
        for _ in range(60):
            await bucket.consume()
        assert bucket.tokens <= 0
        # Manually advance time by 30 seconds
        bucket.last_refill = time.monotonic() - 30
        # Refill happens on next consume
        await bucket.consume()
        assert bucket.tokens >= 29  # should have refilled ~30 tokens

    @pytest.mark.anyio
    async def test_initial_tokens_full(self):
        bucket = TokenBucket(100, 60)
        assert bucket.tokens == 100


class TestPaymentStatusCache:
    @pytest.fixture
    def wallet(self):
        w = MagicMock(spec=BlinkWallet)
        w.payment_status_cache = {}
        w.payment_status_cache_pending_ttl = 30
        w.payment_status_cache_terminal_ttl = 60 * 60 * 24
        w._cache_payment_status = BlinkWallet._cache_payment_status.__get__(w)
        w._get_cached_payment_status = BlinkWallet._get_cached_payment_status.__get__(w)
        return w

    def test_cache_terminal_status(self, wallet):
        status = PaymentStatus(paid=True, fee_msat=1000, preimage="abc")
        wallet._cache_payment_status("hash1", status)
        cached = wallet._get_cached_payment_status("hash1")
        assert cached is not None
        assert cached.paid is True
        assert cached.fee_msat == 1000
        assert cached.preimage == "abc"

    def test_cache_pending_status(self, wallet):
        status = PaymentStatus(paid=None)
        wallet._cache_payment_status("hash2", status)
        cached = wallet._get_cached_payment_status("hash2")
        assert cached is not None
        assert cached.paid is None

    def test_cache_expires_terminal_after_ttl(self, wallet):
        status = PaymentStatus(paid=False)
        wallet._cache_payment_status("hash3", status)
        # Manually expire it
        wallet.payment_status_cache["hash3"]["expires_at"] = time.time() - 1
        cached = wallet._get_cached_payment_status("hash3")
        assert cached is None

    def test_cache_returns_none_for_missing(self, wallet):
        cached = wallet._get_cached_payment_status("nonexistent")
        assert cached is None

    def test_terminal_ttl_longer_than_pending(self, wallet):
        wallet._cache_payment_status("pending", PaymentStatus(paid=None))
        wallet._cache_payment_status("terminal", PaymentStatus(paid=True))

        pending_ttl = wallet.payment_status_cache["pending"]["expires_at"] - time.time()
        terminal_ttl = (
            wallet.payment_status_cache["terminal"]["expires_at"] - time.time()
        )
        assert terminal_ttl > pending_ttl


class TestPendingInvoiceTracking:
    @pytest.fixture
    def wallet(self):
        w = MagicMock(spec=BlinkWallet)
        w.pending_invoices = []
        w.pending_invoice_details = {}
        w.pending_invoices_lookup_cooldown = 1.0
        w.lookup_backoff_schedule = [30, 60, 120, 300, 600, 1200, 1800]
        w._track_pending_invoice = BlinkWallet._track_pending_invoice.__get__(w)
        w._remove_pending_invoice = BlinkWallet._remove_pending_invoice.__get__(w)
        w._schedule_next_lookup = BlinkWallet._schedule_next_lookup.__get__(w)
        w._expire_pending_invoices = BlinkWallet._expire_pending_invoices.__get__(w)
        return w

    def test_track_pending_invoice(self, wallet):
        now = int(time.time())
        wallet._track_pending_invoice("hash1", now, now + 3600)
        assert "hash1" in wallet.pending_invoices
        assert "hash1" in wallet.pending_invoice_details
        assert wallet.pending_invoice_details["hash1"]["created_at"] == now
        assert wallet.pending_invoice_details["hash1"]["lookup_attempts"] == 0

    def test_track_pending_invoice_sets_next_lookup(self, wallet):
        now = int(time.time())
        wallet._track_pending_invoice("hash2", now, now + 3600)
        assert "next_lookup_at" in wallet.pending_invoice_details["hash2"]
        next_at = wallet.pending_invoice_details["hash2"]["next_lookup_at"]
        # First backoff is 30s, so next_lookup_at should be ~now + 30
        assert next_at >= now + 30

    def test_remove_pending_invoice(self, wallet):
        now = int(time.time())
        wallet._track_pending_invoice("hash3", now, now + 3600)
        result = wallet._remove_pending_invoice("hash3")
        assert result is True
        assert "hash3" not in wallet.pending_invoices
        assert "hash3" not in wallet.pending_invoice_details

    def test_remove_nonexistent_returns_false(self, wallet):
        result = wallet._remove_pending_invoice("nonexistent")
        assert result is False

    def test_expire_pending_invoices(self, wallet):
        now = int(time.time())
        wallet._track_pending_invoice("expired1", now - 7200, now - 3600)
        wallet._track_pending_invoice("valid1", now, now + 3600)
        wallet._expire_pending_invoices(now)
        assert "expired1" not in wallet.pending_invoices
        assert "valid1" in wallet.pending_invoices

    def test_schedule_next_lookup_backoff_increases(self, wallet):
        now = float(time.time())
        invoice = {"checking_id": "test", "lookup_attempts": 0}
        wallet._schedule_next_lookup(invoice, now)
        first_delay = invoice["next_lookup_at"] - now

        invoice["lookup_attempts"] = 5
        wallet._schedule_next_lookup(invoice, now)
        fifth_delay = invoice["next_lookup_at"] - now

        assert fifth_delay > first_delay


class TestPayInvoiceDecodeFix:
    @pytest.mark.anyio
    async def test_pay_invoice_returns_pending_on_api_error(self):
        w = MagicMock(spec=BlinkWallet)
        w.pay_invoice = BlinkWallet.pay_invoice.__get__(w)
        w._graphql_query = AsyncMock(side_effect=Exception("Connection failed"))
        w.get_payment_status = AsyncMock()
        w.wallet_id = "test_wallet"

        with patch("lnbits.wallets.blink.bolt11_lib.decode") as mock_decode:
            mock_decode.return_value.payment_hash = "test_payment_hash"
            result = await w.pay_invoice("lnbc1...", fee_limit_msat=1000)

        # Should be pending (ok=None) with checking_id set, not failed
        assert result.ok is None
        assert result.checking_id == "test_payment_hash"
        assert result.error_message is None


class TestConcurrentRequestCoalescing:
    @pytest.mark.anyio
    async def test_coalesces_concurrent_calls(self):
        wallet = cast(BlinkWallet, funding_source)
        wallet._status_locks = {}

        fetch_count = 0

        async def slow_fetch(checking_id):
            nonlocal fetch_count
            fetch_count += 1
            await asyncio.sleep(0.05)
            from lnbits.wallets.base import PaymentStatus

            return PaymentStatus(paid=True)

        wallet._fetch_payment_status = slow_fetch
        wallet._cache_payment_status = BlinkWallet._cache_payment_status.__get__(wallet)
        wallet._get_cached_payment_status = (
            BlinkWallet._get_cached_payment_status.__get__(wallet)
        )
        wallet.get_payment_status = BlinkWallet.get_payment_status.__get__(wallet)

        # Clear cache for the test hash
        wallet.payment_status_cache.pop("concurrent_test", None)

        # Fire 5 concurrent calls
        tasks = [wallet.get_payment_status("concurrent_test") for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(r.paid is True for r in results)
        assert fetch_count == 1
