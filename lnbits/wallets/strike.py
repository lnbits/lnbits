import asyncio
import random
import time
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from loguru import logger

from lnbits.settings import settings

from .base import (
    InvoiceResponse,
    PaymentFailedStatus,
    PaymentPendingStatus,
    PaymentResponse,
    PaymentStatus,
    PaymentSuccessStatus,
    StatusResponse,
    Wallet,
)


class TokenBucket:
    """
    Token bucket rate limiter for Strike API endpoints.
    """

    def __init__(self, rate: int, period_seconds: int):
        """
        Initialize a token bucket.

        Args:
            rate: Max requests allowed in the period
            period_seconds: Time period in seconds.
        """
        self.rate = rate
        self.period = period_seconds
        self.tokens = rate
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self) -> None:
        """Wait until a token is available and consume it."""
        async with self.lock:
            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self.last_refill

            if elapsed > 0:
                new_tokens = int((elapsed / self.period) * self.rate)
                self.tokens = min(self.rate, self.tokens + new_tokens)
                self.last_refill = now

            # If no tokens available, calculate wait time and wait for a token
            if self.tokens < 1:
                # Calculate time needed for one token
                wait_time = (self.period / self.rate) * (1 - self.tokens)
                await asyncio.sleep(wait_time)

                # After waiting, update time and add one token
                self.last_refill = time.monotonic()
                self.tokens = 1

            # Consume a token (will be 0 or more after consumption)
            self.tokens -= 1


class StrikeWallet(Wallet):
    """
    https://developer.strike.me/api
    A minimal LNbits wallet backend for Strike.
    """

    # --------------------------------------------------------------------- #
    # construction / teardown                                               #
    # --------------------------------------------------------------------- #

    def __init__(self):
        if not settings.strike_api_endpoint:
            raise ValueError("Missing strike_api_endpoint")
        if not settings.strike_api_key:
            raise ValueError("Missing strike_api_key")

        super().__init__()

        # tuneables
        self._MAX_PARALLEL_REQUESTS = 20
        self._MAX_RETRIES = 3
        self._RETRY_STATUS = {429, 500, 502, 503, 504}
        self._RETRY_BACKOFF_BASE = 2  # seconds (exponential)

        # throttle
        self._sem = asyncio.Semaphore(self._MAX_PARALLEL_REQUESTS)

        # Rate limiters for different API endpoints
        # Invoice/payment operations: 250 requests / 1 minute
        self._invoice_limiter = TokenBucket(250, 60)
        self._payment_limiter = TokenBucket(250, 60)
        # All other operations: 1,000 requests / 10 minutes
        self._general_limiter = TokenBucket(1000, 600)

        self.client = httpx.AsyncClient(
            base_url=self.normalize_endpoint(settings.strike_api_endpoint),
            headers={
                "Authorization": f"Bearer {settings.strike_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": settings.user_agent,
            },
            timeout=httpx.Timeout(connect=5.0, read=40.0, write=10.0, pool=None),
            transport=httpx.AsyncHTTPTransport(
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
                retries=0,  # we handle retries ourselves
            ),
        )

        # runtime state
        self.pending_invoices: list[str] = []  # Keep it as a list
        self.pending_payments: Dict[str, str] = {}
        self.failed_payments: Dict[str, str] = {}

        # balance cache
        self._cached_balance: Optional[int] = None
        self._cached_balance_ts: float = 0.0
        self._cache_ttl = 30  # seconds

    async def cleanup(self):
        try:
            await self.client.aclose()
        except Exception:
            logger.warning("Error closing Strike client")

    # --------------------------------------------------------------------- #
    # low-level request helpers                                             #
    # --------------------------------------------------------------------- #

    async def _req(self, method: str, path: str, /, **kw) -> httpx.Response:
        """Make a Strike HTTP call with:
        One Strike HTTP call with
            • rate limiting based on endpoint type
            • concurrency throttle
            • exponential back-off + jitter
            • explicit retry on 429/5xx
            • latency logging
        """
        # Apply the appropriate rate limiter based on the endpoint path.
        if path.startswith("/invoices") or path.startswith("/receive-requests"):
            await self._invoice_limiter.consume()
        elif path.startswith("/payment-quotes"):
            await self._payment_limiter.consume()
        else:
            await self._general_limiter.consume()

        async with self._sem:
            start = time.perf_counter()

            for attempt in range(self._MAX_RETRIES + 1):
                try:
                    resp = await self.client.request(method, path, **kw)
                    resp.raise_for_status()
                    logger.trace(
                        f"Strike {method.upper()} {path} - {resp.status_code} "
                        f"in {(time.perf_counter() - start) * 1000:.1f} ms"
                    )
                    return resp

                except httpx.HTTPStatusError as e:
                    if (  # Only retry on specific status codes.
                        e.response.status_code not in self._RETRY_STATUS
                        or attempt == self._MAX_RETRIES
                    ):
                        raise
                    logger.warning(
                        f"Strike {method.upper()} {path} -> {e.response.status_code}; "
                        f"retry {attempt + 1}/{self._MAX_RETRIES}"
                    )

                except httpx.TransportError as e:
                    if attempt == self._MAX_RETRIES:  # No more retries left.
                        raise
                    logger.warning(
                        f"Transport error contacting Strike ({e}); "
                        f"retry {attempt + 1}/{self._MAX_RETRIES}"
                    )

                delay = (self._RETRY_BACKOFF_BASE**attempt) + (
                    0.1 * random.random()
                )  # Exponential backoff with jitter.
                await asyncio.sleep(delay)

        raise RuntimeError("exceeded retry budget in _req")

    # Typed wrappers - so call-sites stay tidy.
    async def _get(self, path: str, **kw) -> httpx.Response:  # GET request.
        return await self._req("GET", path, **kw)

    async def _post(self, path: str, **kw) -> httpx.Response:
        return await self._req("POST", path, **kw)

    async def _patch(self, path: str, **kw) -> httpx.Response:
        return await self._req("PATCH", path, **kw)

    # --------------------------------------------------------------------- #
    # LNbits wallet API implementation                                      #
    # --------------------------------------------------------------------- #

    async def status(self) -> StatusResponse:
        """
        Return wallet balance (millisatoshis) with a 30-second cache.
        """
        now = time.time()
        if (
            self._cached_balance is not None
            and now - self._cached_balance_ts < self._cache_ttl
        ):
            return StatusResponse(None, self._cached_balance)

        try:
            r = await self._get("/balances")  # Get balances from Strike API.
            data = r.json()  # Parse JSON response.
            balances = (
                data.get("data", []) if isinstance(data, dict) else data
            )  # Extract balances or use an empty list.
            btc = next(
                (b for b in balances if b.get("currency") == "BTC"), None
            )  # Find BTC balance.
            if (
                btc and "available" in btc
            ):  # Check if BTC balance and available amount exist.
                available_btc = Decimal(btc["available"])  # Get available BTC amount.
                msats = int(
                    available_btc * Decimal(1e11)
                )  # Convert BTC to millisatoshis.
                self._cached_balance = msats  # Update cached balance.
                self._cached_balance_ts = now  # Update cache timestamp.
                return StatusResponse(
                    None, msats
                )  # Return successful status with balance.
            # No BTC balance found.
            return StatusResponse(None, 0)
        except httpx.HTTPStatusError as e:
            logger.warning(f"Strike API error: {e.response.text}")
            return StatusResponse(f"Strike API error: {e.response.text}", 0)
        except Exception:
            logger.warning("Unexpected error in status()")
            return StatusResponse("Connection error", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        unhashed_description: bytes | None = None,  # Add this parameter
        **kwargs,
    ) -> InvoiceResponse:
        try:
            btc_amt = (Decimal(amount) / Decimal(1e8)).quantize(
                Decimal("0.00000001")
            )  # Convert amount from millisatoshis to BTC.
            payload: Dict[str, Any] = {
                "bolt11": {
                    "amount": {
                        "currency": "BTC",
                        "amount": str(btc_amt),
                    },
                    "description": memo or "",
                },
                "targetCurrency": "BTC",
            }
            if description_hash:
                payload["bolt11"]["descriptionHash"] = description_hash.hex()

            r = await self._post(
                "/receive-requests",  # Create a receive request (invoice) on Strike.
                json=payload,
            )
            resp = r.json()
            invoice_id = resp.get("receiveRequestId")
            bolt11 = resp.get("bolt11", {}).get("invoice")
            if not invoice_id or not bolt11:
                return InvoiceResponse(
                    ok=False, error_message="Invalid invoice response"
                )

            self.pending_invoices.append(invoice_id)
            return InvoiceResponse(
                ok=True, checking_id=invoice_id, payment_request=bolt11
            )
        except httpx.HTTPStatusError as e:
            logger.warning(e)
            msg = e.response.json().get(
                "message", e.response.text
            )  # Get error message from response.
            return InvoiceResponse(ok=False, error_message=f"Strike API error: {msg}")
        except Exception as e:
            logger.warning(e)
            return InvoiceResponse(ok=False, error_message="Connection error")

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            # 1) Create a payment quote.
            q = await self._post(
                "/payment-quotes/lightning",
                json={"lnInvoice": bolt11},
            )
            q.raise_for_status()
            quote_id = q.json().get("paymentQuoteId")
            if not quote_id:
                return PaymentResponse(
                    ok=False, error_message="Strike: missing payment quote Id"
                )

            # 2) Execute the payment quote.
            e = await self._patch(f"/payment-quotes/{quote_id}/execute")
            e.raise_for_status()

            data = e.json() if e.content else {}
            payment_id = data.get("paymentId")
            state = data.get("state", "").upper()

            # Network fee → msat.
            fee_obj = data.get("lightningNetworkFee") or data.get("totalFee") or {}
            fee_btc = Decimal(fee_obj.get("amount", "0"))
            fee_msat = int(fee_btc * Decimal(1e11))  # millisatoshis.

            if state in {"SUCCEEDED", "COMPLETED"}:
                preimage = data.get("preimage") or data.get("preImage")
                return PaymentResponse(
                    ok=True,
                    checking_id=payment_id,
                    fee_msat=fee_msat,
                    preimage=preimage,
                )

            failed_states = {
                "CANCELED",
                "FAILED",
                "TIMED_OUT",
            }
            if state in failed_states:
                return PaymentResponse(
                    ok=False, checking_id=payment_id, error_message=f"State: {state}"
                )

            # Store mapping for later polling.
            if payment_id:
                # todo: this will be lost on server restart
                self.pending_payments[payment_id] = quote_id

            # Treat all other states as pending (including unknown states).
            return PaymentResponse(ok=None, checking_id=payment_id)

        except Exception as e:
            logger.warning(e)
            # Keep pending. Not sure if the payment went trough or not.
            return PaymentResponse(ok=None, error_message="Connection error")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self._get(f"/receive-requests/{checking_id}/receives")
            if r.status_code == 404:
                # Try getting invoice from the old endpoint with correct path.
                r2 = await self._get(f"/v1/invoices/{checking_id}")
                st = r2.json().get("state", "")
                if st == "PAID":
                    return PaymentSuccessStatus(fee_msat=0)
                if st == "CANCELLED":
                    return PaymentFailedStatus(False)
                return PaymentPendingStatus()

            r.raise_for_status()
            for itm in r.json().get("items", []):
                if itm.get("state") == "COMPLETED":
                    preimage = None
                    data = itm.get("lightning")
                    if data:
                        preimage = data.get("preimage") or data.get("preImage")
                    return PaymentSuccessStatus(fee_msat=0, preimage=preimage)
            return PaymentPendingStatus()

        except Exception as e:
            logger.warning(e)
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        quote_id = self.pending_payments.get(checking_id)
        if not quote_id:
            if checking_id in self.failed_payments:
                return PaymentFailedStatus()
            # todo: it will stop here for all payments
            # todo: after a server restart
            return PaymentPendingStatus()
        try:
            r = await self._get(f"/payment-quotes/{quote_id}")
            if r.status_code == 404:
                # Quote not found, likely expired or payment failed.
                self.pending_payments.pop(checking_id, None)
                self.failed_payments[checking_id] = quote_id
                return PaymentFailedStatus()
            r.raise_for_status()

            data = r.json()
            state = data.get("state")
            preimage = data.get("preimage") or data.get("preImage")
            if state in {"SUCCEEDED", "COMPLETED"}:
                return PaymentSuccessStatus(fee_msat=0, preimage=preimage)
            if state == "FAILED":
                return PaymentFailedStatus()
            # Default to pending for PENDING and any other states
            return PaymentPendingStatus()
        except Exception as e:
            logger.warning(e)
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        """
        Poll Strike for invoice settlement while respecting the documented API limits.

        Uses dynamic adjustment of polling frequency based on activity.
        """
        min_poll, max_poll = 1, 15
        # 1,000 requests / 10 minutes = ~100 requests/minute.
        rate_limit = 100
        sleep_s = min_poll
        # Main loop for polling invoices.
        self._running = True

        while self._running and settings.lnbits_running:
            loop_start = time.time()
            had_activity = False

            req_budget = max(
                1, rate_limit * sleep_s // 60
            )  # Calculate request budget based on sleep time.
            processed = 0

            for inv in list(self.pending_invoices):
                if processed >= req_budget:  # If request budget is exhausted.
                    break
                status = await self.get_invoice_status(inv)
                processed += 1

                if status.success or status.failed:
                    self.pending_invoices.remove(inv)
                    if status.success:
                        had_activity = True
                        yield inv

            # Dynamic adjustment of polling frequency based on activity.
            sleep_s = (
                max(min_poll, sleep_s // 2)
                if had_activity
                else min(max_poll, sleep_s * 2)
            )

            # Sleep to respect rate limits.
            elapsed = time.time() - loop_start
            # Ensure we respect the rate limit, even with dynamic adjustment.
            min_sleep_for_rate = processed * 60 / rate_limit - elapsed
            await asyncio.sleep(max(sleep_s, min_sleep_for_rate, 0))

    # ------------------------------------------------------------------ #
    # misc Strike helpers                                                #
    # ------------------------------------------------------------------ #

    async def get_invoices(
        self,
        filters: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: Optional[int] = None,
        top: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            params: Dict[str, Any] = {}
            if filters:
                params["$filter"] = filters
            if orderby:
                params["$orderby"] = orderby
            if skip is not None:
                params["$skip"] = skip
            if top is not None:
                params["$top"] = top
            r = await self._get(
                "/invoices", params=params
            )  # Get invoices from Strike API.
            return r.json()
        except Exception:
            logger.warning("Error in get_invoices()")
            return {"error": "unable to fetch invoices"}
