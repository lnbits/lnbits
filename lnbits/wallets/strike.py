import asyncio
import random
import time
import traceback
import uuid
from decimal import Decimal
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from loguru import logger

from lnbits.settings import settings
from .base import (
    InvoiceResponse,
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
            period_seconds: Time period in seconds
        """
        self.rate = rate
        self.period = period_seconds
        self.tokens = rate
        self.last_refill = time.monotonic()
        self.lock = asyncio.Lock()
    
    async def consume(self) -> None:
        """Wait until a token is available and consume it"""
        async with self.lock:
            # Refill tokens based on elapsed time
            now = time.monotonic()
            elapsed = now - self.last_refill
            
            if elapsed > 0:
                new_tokens = (elapsed / self.period) * self.rate
                self.tokens = min(self.rate, self.tokens + new_tokens)
                self.last_refill = now
            
            # If no tokens available, calculate wait time
            if self.tokens < 1:
                wait_time = (self.period / self.rate) * (1 - self.tokens)
                await asyncio.sleep(wait_time)
                self.tokens = 0  # Reset after waiting
            
            # Consume a token
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
        self.pending_invoices: set[str] = set()
        self.pending_payments: Dict[str, str] = {}

        # balance cache
        self._cached_balance: Optional[int] = None
        self._cached_balance_ts: float = 0.0
        self._cache_ttl = 30  # seconds

    async def cleanup(self):
        try:
            await self.client.aclose()
        except Exception:
            logger.exception("Error closing Strike client")

    # --------------------------------------------------------------------- #
    # low-level request helpers                                             #
    # --------------------------------------------------------------------- #

    async def _req(self, method: str, path: str, /, **kw) -> httpx.Response:
        """
        One Strike HTTP call with
            • rate limiting based on endpoint type
            • concurrency throttle
            • exponential back-off + jitter
            • explicit retry on 429/5xx
            • latency logging
        """
        # Apply appropriate rate limiter based on endpoint path
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
                    logger.debug(
                        "Strike {m} {p} – {s} in {t:.1f} ms".format(
                            m=method.upper(),
                            p=path,
                            s=resp.status_code,
                            t=(time.perf_counter() - start) * 1000,
                        )
                    )
                    return resp

                except httpx.HTTPStatusError as e:
                    if (
                        e.response.status_code not in self._RETRY_STATUS
                        or attempt == self._MAX_RETRIES
                    ):
                        raise
                    logger.warning(
                        "Strike {m} {p} -> {c}; retry {a}/{n}".format(
                            m=method.upper(),
                            p=path,
                            c=e.response.status_code,
                            a=attempt + 1,
                            n=self._MAX_RETRIES,
                        )
                    )

                except httpx.TransportError as e:
                    if attempt == self._MAX_RETRIES:
                        raise
                    logger.warning(
                        "Transport error contacting Strike ({err}); retry {a}/{n}".format(
                            err=e, a=attempt + 1, n=self._MAX_RETRIES
                        )
                    )

                delay = (self._RETRY_BACKOFF_BASE ** attempt) + (0.1 * random.random())
                await asyncio.sleep(delay)

        raise RuntimeError("exceeded retry budget in _req")

    # typed wrappers – so call-sites stay tidy
    async def _get(self, path: str, **kw) -> httpx.Response:
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
        Return wallet balance (millisatoshis) with 30 s cache.
        """
        now = time.time()
        if (
            self._cached_balance is not None
            and now - self._cached_balance_ts < self._cache_ttl
        ):
            return StatusResponse(None, self._cached_balance)

        try:
            r = await self._get("/balances")
            data = r.json()
            balances = data.get("data", []) if isinstance(data, dict) else data
            btc = next((b for b in balances if b.get("currency") == "BTC"), None)
            if btc and "available" in btc:
                available_btc = Decimal(btc["available"])
                msats = int(available_btc * Decimal(1e11))
                self._cached_balance = msats
                self._cached_balance_ts = now
                return StatusResponse(None, msats)

            return StatusResponse(None, 0)
        except httpx.HTTPStatusError as e:
            logger.error(f"Strike API error: {e.response.text}")
            return StatusResponse(f"Strike API error: {e.response.text}", 0)
        except Exception:
            logger.exception("Unexpected error in status()")
            return StatusResponse("Connection error", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: Optional[str] = None,
        description_hash: Optional[bytes] = None,
        **kwargs,
    ) -> InvoiceResponse:
        try:
            idem = kwargs.get("idempotency_key") or str(uuid.uuid4())
            btc_amt = (Decimal(amount) / Decimal(1e8)).quantize(Decimal("0.00000001"))
            payload: Dict[str, Any] = {
                "bolt11": {
                    "amount": {"currency": "BTC", "amount": str(btc_amt)},
                    "description": memo or "",
                },
                "targetCurrency": "BTC",
            }
            if description_hash:
                payload["bolt11"]["descriptionHash"] = description_hash.hex()

            r = await self._post(
                "/receive-requests",
                json=payload,
                headers={**self.client.headers, "idempotency-key": idem},
            )
            resp = r.json()
            invoice_id = resp.get("receiveRequestId")
            bolt11 = resp.get("bolt11", {}).get("invoice")
            if not invoice_id or not bolt11:
                return InvoiceResponse(False, None, None, "Invalid invoice response")

            self.pending_invoices.add(invoice_id)
            return InvoiceResponse(True, invoice_id, bolt11, None)
        except httpx.HTTPStatusError as e:
            msg = e.response.json().get("message", e.response.text)
            return InvoiceResponse(False, None, None, f"Strike API error: {msg}")
        except Exception:
            logger.exception("Error in create_invoice()")
            return InvoiceResponse(False, None, None, "Connection error")

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            idem = str(uuid.uuid4())

            # 1) create quote
            q = await self._post(
                "/payment-quotes/lightning",
                json={"lnInvoice": bolt11},
                headers={**self.client.headers, "idempotency-key": idem},
            )
            quote_id = q.json().get("paymentQuoteId")
            if not quote_id:
                return PaymentResponse(
                    False, None, None, None, "Strike: missing paymentQuoteId"
                )

            # 2) execute quote
            e = await self._patch(f"/payment-quotes/{quote_id}/execute")
            data = e.json() if e.content else {}
            payment_id = data.get("paymentId")
            state = data.get("state", "").upper()

            # network fee → msat
            fee_obj = data.get("lightningNetworkFee") or data.get("totalFee") or {}
            fee_btc = Decimal(fee_obj.get("amount", "0"))
            fee_msat = int(fee_btc * Decimal(1e11))

            # store mapping for later polling
            if payment_id:
                self.pending_payments[payment_id] = quote_id

            if state in {"SUCCEEDED", "COMPLETED"}:
                preimage = data.get("preimage") or data.get("preImage")
                return PaymentResponse(True, payment_id, fee_msat, preimage, None)

            # Strike often returns 202/PENDING immediately; treat as “still working”
            if state in {"PENDING", "QUEUED", "READY_TO_SETTLE", ""}:
                return PaymentResponse(None, payment_id, None, None, None)

            return PaymentResponse(False, payment_id, None, None, f"State: {state}")

        except httpx.HTTPStatusError as e:
            msg = e.response.json().get("message", e.response.text)
            return PaymentResponse(False, None, None, None, f"Strike API error: {msg}")
        except Exception:
            logger.exception("Error in pay_invoice()")
            return PaymentResponse(False, None, None, None, "Connection error")


    async def get_invoice_status(self, invoice_id: str) -> PaymentStatus:
        try:
            r = await self._get(f"/receive-requests/{invoice_id}/receives")
            for itm in r.json().get("items", []):
                if itm.get("state") == "COMPLETED":
                    return PaymentSuccessStatus(fee_msat=0)
            return PaymentPendingStatus()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                try:
                    r2 = await self._get(f"/invoices/{invoice_id}")
                    st = r2.json().get("state", "")
                    if st == "PAID":
                        return PaymentSuccessStatus(fee_msat=0)
                    if st == "CANCELLED":
                        return PaymentStatus(False)
                except Exception:
                    pass
            return PaymentPendingStatus()
        except Exception:
            logger.exception("Error in get_invoice_status()")
            return PaymentPendingStatus()

    async def get_payment_status(self, payment_id: str) -> PaymentStatus:
        quote_id = self.pending_payments.get(payment_id)
        if not quote_id:
            return PaymentPendingStatus()
        try:
            r = await self._get(f"/payment-quotes/{quote_id}")
            data = r.json()
            state = data.get("state")
            preimage = data.get("preimage") or data.get("preImage")
            if state in ("SUCCEEDED", "COMPLETED"):
                return PaymentSuccessStatus(fee_msat=0, preimage=preimage)
            if state == "PENDING":
                return PaymentPendingStatus()
            return PaymentStatus(False)
        except Exception:
            logger.exception("Error in get_payment_status()")
            return PaymentPendingStatus()

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        """
        Poll Strike for invoice settlement while respecting the
        documented API limits:
        - "All others" category: 1,000 requests / 10 minutes (which get_invoice_status falls under)
        """
        MIN_POLL, MAX_POLL = 1, 15
        # 1,000 requests / 10 minutes = ~100 requests/minute
        RATE_LIMIT = 100
        sleep_s = MIN_POLL
        self._running = True

        while self._running and settings.lnbits_running:
            loop_start = time.time()
            had_activity = False

            req_budget = max(1, RATE_LIMIT * sleep_s // 60)
            processed = 0

            for inv in list(self.pending_invoices):
                if processed >= req_budget:
                    break
                status = await self.get_invoice_status(inv)
                processed += 1

                if status.success or status.failed:
                    self.pending_invoices.discard(inv)
                    if status.success:
                        had_activity = True
                        yield inv

            # Dynamic adjustment of polling frequency based on activity
            sleep_s = (
                max(MIN_POLL, sleep_s // 2) if had_activity else min(MAX_POLL, sleep_s * 2)
            )

            elapsed = time.time() - loop_start
            min_sleep_for_rate = processed * 60 / RATE_LIMIT - elapsed
            await asyncio.sleep(max(sleep_s, min_sleep_for_rate, 0))

    # ------------------------------------------------------------------ #
    # misc Strike helpers                                                #
    # ------------------------------------------------------------------ #

    async def get_invoices(
        self,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: Optional[int] = None,
        top: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            params: Dict[str, Any] = {}
            if filter:
                params["$filter"] = filter
            if orderby:
                params["$orderby"] = orderby
            if skip is not None:
                params["$skip"] = skip
            if top is not None:
                params["$top"] = top
            r = await self._get("/invoices", params=params)
            return r.json()
        except Exception:
            logger.exception("Error in get_invoices()")
            return {"error": "unable to fetch invoices"}

    async def cancel_invoice(self, invoice_id: str) -> Dict[str, Any]:
        try:
            r = await self._patch(f"/invoices/{invoice_id}/cancel")
            return r.json()
        except Exception:
            logger.exception("Error in cancel_invoice()")
            return {"error": "unable to cancel invoice"}

    async def get_account_profile_by_handle(self, handle: str) -> Dict[str, Any]:
        try:
            r = await self._get(f"/accounts/handle/{handle}")
            return r.json()
        except Exception:
            logger.exception("Error in get_account_profile_by_handle()")
            return {"error": "unable to fetch profile"}
