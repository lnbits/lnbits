import asyncio
import random
import time
import uuid
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
            logger.exception("Error closing Strike client")

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
        unhashed_description: bytes | None = None,  # Add this parameter
        **kwargs,
    ) -> InvoiceResponse:
        try:
            idem = kwargs.get("idempotency_key") or str(
                uuid.uuid4()
            )  # Use provided idempotency key or generate a new one.
            btc_amt = (Decimal(amount) / Decimal(1e8)).quantize(
                Decimal("0.00000001")
            )  # Convert amount from millisatoshis to BTC.
            payload: Dict[str, Any] = {
                "bolt11": {
                    "amount": {
                        "currency": "BTC",
                        "amount": str(btc_amt),
                    },  # Set amount in BTC.
                    "description": memo or "",
                },
                "targetCurrency": "BTC",
            }
            if description_hash:
                payload["bolt11"]["descriptionHash"] = description_hash.hex()

            r = await self._post(
                "/receive-requests",  # Create a receive request (invoice) on Strike.
                json=payload,
                headers={**self.client.headers, "idempotency-key": idem},
            )
            resp = r.json()  # Parse JSON response.
            invoice_id = resp.get("receiveRequestId")  # Get the receive request ID.
            bolt11 = resp.get("bolt11", {}).get("invoice")  # Get the bolt11 invoice.
            if (
                not invoice_id or not bolt11
            ):  # Check if both invoice ID and bolt11 are present.
                return InvoiceResponse(False, None, None, "Invalid invoice response")

            self.pending_invoices.append(
                invoice_id
            )  # Add invoice ID to pending invoices.
            return InvoiceResponse(
                True, invoice_id, bolt11, None
            )  # Return successful invoice response.
        except httpx.HTTPStatusError as e:
            msg = e.response.json().get(
                "message", e.response.text
            )  # Get error message from response.
            return InvoiceResponse(False, None, None, f"Strike API error: {msg}")
        except Exception:
            logger.exception("Error in create_invoice()")
            return InvoiceResponse(False, None, None, "Connection error")

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        try:
            idem = str(uuid.uuid4())
            # 1) Create a payment quote.
            q = await self._post(
                "/payment-quotes/lightning",
                json={"lnInvoice": bolt11},
                headers={**self.client.headers, "idempotency-key": idem},
            )
            quote_id = q.json().get("paymentQuoteId")  # Get the payment quote ID.
            if not quote_id:  # Check if the quote ID is present.
                return PaymentResponse(
                    False, None, None, None, "Strike: missing paymentQuoteId"
                )

            # 2) Execute the payment quote.
            e = await self._patch(f"/payment-quotes/{quote_id}/execute")
            data = (
                e.json() if e.content else {}
            )  # Parse JSON response or use an empty dictionary.
            payment_id = data.get("paymentId")  # Get the payment ID.
            state = data.get(
                "state", ""
            ).upper()  # Get the payment state and convert it to uppercase.

            # Network fee → msat.
            fee_obj = (
                data.get("lightningNetworkFee") or data.get("totalFee") or {}
            )  # Get fee object.
            fee_btc = Decimal(fee_obj.get("amount", "0"))  # Get fee amount in BTC.
            fee_msat = int(
                fee_btc * Decimal(1e11)
            )  # Convert fee from BTC to millisatoshis.

            # Store mapping for later polling.
            if payment_id:  # If payment ID is present.
                self.pending_payments[payment_id] = quote_id

            if state in {"SUCCEEDED", "COMPLETED"}:  # If payment succeeded.
                preimage = data.get("preimage") or data.get(
                    "preImage"
                )  # Get payment preimage.
                return PaymentResponse(
                    True, payment_id, fee_msat, preimage, None
                )  # Return successful payment response.

            # Explicitly check for known failure states.
            failed_states = {
                "CANCELED",
                "FAILED",
                "TIMED_OUT",
            }  # Add any other known failure states here.
            if state in failed_states:
                return PaymentResponse(
                    False, payment_id, None, None, f"State: {state}"
                )  # Return failed payment response with state.

            # Treat all other states as pending (including unknown states).
            return PaymentResponse(
                None, payment_id, None, None, None
            )  # Return pending payment response.

        except httpx.HTTPStatusError as e:
            error_message = e.response.json().get(
                "message", e.response.text
            )  # Get error message from response.
            return PaymentResponse(
                ok=False,
                checking_id=None,
                fee_msat=None,
                preimage=None,
                error_message=f"Strike API error: {error_message}",
            )  # Return payment response with error.
        except Exception:
            logger.exception("Error in pay_invoice()")
            return PaymentResponse(False, None, None, None, "Connection error")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self._get(
                f"/receive-requests/{checking_id}/receives"
            )  # Get receive requests for the invoice.
            for itm in r.json().get("items", []):  # Iterate through received items.
                if itm.get("state") == "COMPLETED":  # If an item is completed.
                    # Extract preimage from lightning object if available
                    preimage = None
                    lightning_data = itm.get("lightning")
                    if lightning_data:
                        preimage = lightning_data.get("preimage")
                    return PaymentSuccessStatus(
                        fee_msat=0, preimage=preimage
                    )  # Return successful payment status with preimage.
            return (
                PaymentPendingStatus()
            )  # Return pending payment status if no completed items.
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:  # If invoice not found.
                try:
                    r2 = await self._get(
                        f"/v1/invoices/{checking_id}"
                    )  # Try getting invoice from the old endpoint with correct path.
                    st = r2.json().get("state", "")  # Get invoice state.
                    if st == "PAID":  # If invoice is paid.
                        return PaymentSuccessStatus(
                            fee_msat=0
                        )  # Return successful payment status.
                    if st == "CANCELLED":  # If invoice is cancelled.
                        return PaymentStatus(False)  # Return failed payment status.
                except Exception:
                    pass  # Ignore exceptions from the old endpoint.
            return PaymentPendingStatus()  # Return pending payment status.
        except Exception:  # Handle other exceptions.
            logger.exception("Error in get_invoice_status()")
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        quote_id = self.pending_payments.get(checking_id)
        if not quote_id:  # Payment not found in pending list.
            if checking_id in self.failed_payments:
                return PaymentFailedStatus(
                    paid=False
                )  # Payment is known to have failed.
            return PaymentPendingStatus()
        try:  # Try to get payment quote.
            r = await self._get(
                f"/payment-quotes/{quote_id}"
            )  # Get payment quote from Strike API.
            r.raise_for_status()
            data = r.json()  # Parse JSON response.
            state = data.get("state")  # Get payment state.
            preimage = data.get("preimage") or data.get(
                "preImage"
            )  # Get payment preimage.
            if state in ("SUCCEEDED", "COMPLETED"):  # If payment succeeded.
                return PaymentSuccessStatus(
                    fee_msat=0, preimage=preimage
                )  # Return successful payment status.
            if state == "PENDING":  # If payment is pending.
                return PaymentPendingStatus()  # Return pending payment status.
            return PaymentStatus(False)  # Return failed payment status.
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Quote not found, likely expired or payment failed.
                self.pending_payments.pop(checking_id, None)
                self.failed_payments[checking_id] = quote_id
                return PaymentFailedStatus(paid=False)
            raise  # Re-raise other HTTP errors
        except Exception:  # Handle exceptions.
            logger.exception(f"Error in get_payment_status() for payment {checking_id}")
            return PaymentPendingStatus()  # Treat as pending for now.

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

            for inv in list(self.pending_invoices):  # Iterate through pending invoices.
                if processed >= req_budget:  # If request budget is exhausted.
                    break
                status = await self.get_invoice_status(inv)  # Get invoice status.
                processed += 1  # Increment processed count.

                if (
                    status.success or status.failed
                ):  # If invoice is either successful or failed.
                    self.pending_invoices.remove(
                        inv
                    )  # Remove invoice from pending list.
                    if status.success:  # If invoice is successful.
                        had_activity = True  # Set activity flag.
                        yield inv  # Yield the invoice.

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
            logger.exception("Error in get_invoices()")
            return {"error": "unable to fetch invoices"}

    async def cancel_invoice(self, invoice_id: str) -> Dict[str, Any]:
        try:
            r = await self._patch(
                f"/invoices/{invoice_id}/cancel"
            )  # Cancel invoice on Strike.
            return r.json()
        except Exception:
            logger.exception("Error in cancel_invoice()")
            return {"error": "unable to cancel invoice"}

    async def get_account_profile_by_handle(self, handle: str) -> Dict[str, Any]:
        try:
            r = await self._get(
                f"/accounts/handle/{handle}"
            )  # Get account profile by handle from Strike API.
            return r.json()
        except Exception:
            logger.exception("Error in get_account_profile_by_handle()")
            return {"error": "unable to fetch profile"}
