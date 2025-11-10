import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from decimal import Decimal
from typing import Any

import httpx
from bolt11 import decode as bolt11_decode
from loguru import logger

from lnbits.helpers import normalize_endpoint
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

    def __init__(self, rate: int, period_seconds: int) -> None:
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

    def __init__(self) -> None:
        if not settings.strike_api_endpoint:
            raise ValueError("Missing strike_api_endpoint")
        if not settings.strike_api_key:
            raise ValueError("Missing strike_api_key")

        super().__init__()

        # throttle
        self._sem = asyncio.Semaphore(value=20)

        # Rate limiters for different API endpoints
        # Invoice/payment operations: 250 requests / 1 minute
        self._invoice_limiter = TokenBucket(250, 60)
        self._payment_limiter = TokenBucket(250, 60)
        # All other operations: 1,000 requests / 10 minutes
        self._general_limiter = TokenBucket(1000, 600)

        self.client = httpx.AsyncClient(
            base_url=normalize_endpoint(settings.strike_api_endpoint),
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

        self.pending_invoices: list[str] = []  # Keep it as a list
        # path for persisting pending invoices
        self.state_path = os.path.join(
            settings.lnbits_data_folder, "strike_pending_invoices.json"
        )
        # load persisted pending invoices
        try:
            with open(self.state_path) as f:
                self.pending_invoices = json.load(f)
        except Exception:
            self.pending_invoices = []
        self.pending_payments: dict[str, str] = {}
        self.failed_payments: dict[str, str] = {}

        # balance cache
        self._cached_balance: int | None = None
        self._cached_balance_ts: float = 0.0
        self._cache_ttl = 30  # seconds

    async def cleanup(self) -> None:
        try:
            await self.client.aclose()
        except Exception:
            logger.warning("Error closing Strike client")

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
            r = await self._get("/balances")
            r.raise_for_status()
            data = r.json()
            balances = data.get("data", []) if isinstance(data, dict) else data
            btc = next((b for b in balances if b.get("currency") == "BTC"), None)
            if btc and "available" in btc:
                available_btc = Decimal(btc["available"])  # Get available BTC amount.
                msats = int(
                    available_btc * Decimal("1e11")
                )  # Convert BTC to millisatoshis.
                self._cached_balance = msats
                self._cached_balance_ts = now
                return StatusResponse(None, msats)

            return StatusResponse(None, 0)

        except Exception as e:
            logger.warning(e)
            return StatusResponse("Connection error", 0)

    async def create_invoice(
        self,
        amount: int,
        memo: str | None = None,
        description_hash: bytes | None = None,
        unhashed_description: bytes | None = None,  # Add this parameter
        **kwargs,
    ) -> InvoiceResponse:
        try:
            btc_amt = (Decimal(amount) / Decimal("1e8")).quantize(
                Decimal("0.00000001")
            )  # Convert amount from millisatoshis to BTC.
            payload: dict[str, Any] = {
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
                "/receive-requests",
                json=payload,
            )
            r.raise_for_status()
            resp = r.json()
            invoice_id = resp.get("receiveRequestId")
            bolt11 = resp.get("bolt11", {}).get("invoice")
            if not invoice_id or not bolt11:
                return InvoiceResponse(
                    ok=False, error_message="Invalid invoice response"
                )

            self.pending_invoices.append(invoice_id)
            self._persist_pending()
            return InvoiceResponse(
                ok=True, checking_id=invoice_id, payment_request=bolt11
            )
        except httpx.HTTPStatusError as e:
            logger.warning(e)
            msg = e.response.json().get("message", e.response.text)
            return InvoiceResponse(ok=False, error_message=f"Strike API error: {msg}")
        except Exception as e:
            logger.warning(e)
            return InvoiceResponse(ok=False, error_message="Connection error")

    async def pay_invoice(self, bolt11: str, fee_limit_msat: int) -> PaymentResponse:
        # Extract payment hash from invoice for checking_id

        try:
            invoice = bolt11_decode(bolt11)
            payment_hash = invoice.payment_hash
        except Exception as decode_exc:
            logger.warning(f"Strike: Failed to decode invoice: {decode_exc}")
            return PaymentResponse(
                ok=False, error_message=f"Invalid invoice: {decode_exc!s}"
            )

        try:
            # 1) Create a payment quote
            quote_id, error = await self._create_payment_quote(bolt11)
            if error or not quote_id:
                return PaymentResponse(ok=False, error_message=error or "Unknown error")

            # 2) Execute the payment quote
            data, error = await self._execute_payment_quote(quote_id)
            if error or not data:
                return PaymentResponse(ok=False, error_message=error or "Unknown error")

            state = data.get("state", "").upper()
            payment_id = data.get("paymentId")

            # Parse fee
            fee_msat = self._parse_payment_fee(data, payment_id or "")

            # Handle successful payment
            if state in {"SUCCEEDED", "COMPLETED"}:
                preimage = self._extract_preimage(data)
                return PaymentResponse(
                    ok=True,
                    checking_id=payment_hash,
                    fee_msat=fee_msat,
                    preimage=preimage,
                )

            # Handle failed payment
            failed_states = {"CANCELED", "FAILED", "TIMED_OUT"}
            if state in failed_states:
                logger.warning(
                    f"Strike payment {payment_id} failed with state: {state}"
                )
                return PaymentResponse(
                    ok=False,
                    checking_id=payment_hash,
                    error_message=f"Payment {state.lower()}",
                )

            # Store mapping for later polling
            self.pending_payments[payment_hash] = quote_id

            # Treat all other states as pending
            return PaymentResponse(ok=None, checking_id=payment_hash)

        except httpx.HTTPStatusError as http_exc:
            logger.warning(f"Strike HTTP error during payment: {http_exc}")
            logger.warning(
                f"Response status: {http_exc.response.status_code}, "
                f"body: {http_exc.response.text}"
            )
            return PaymentResponse(
                ok=False,
                error_message=f"Strike API error: {http_exc.response.status_code}",
            )
        except Exception as e:
            logger.warning(f"Strike payment exception: {e}", exc_info=True)
            return PaymentResponse(ok=None, error_message=f"Error: {e!s}")

    async def get_invoice_status(self, checking_id: str) -> PaymentStatus:
        try:
            r = await self._get(f"/receive-requests/{checking_id}/receives")

            if r.status_code == 200:
                data = r.json()
                items = data.get("items", [])

                if not items:
                    # Still pending.
                    return PaymentPendingStatus()

                for item in items:
                    if item.get("state") == "COMPLETED":
                        preimage = None
                        lightning_data = item.get("lightning")
                        if lightning_data:
                            preimage = lightning_data.get(
                                "preimage"
                            ) or lightning_data.get("preImage")

                        return PaymentSuccessStatus(fee_msat=0, preimage=preimage)

                return PaymentPendingStatus()

            if r.status_code == 404:
                logger.warning(f"Payment '{checking_id}' not found. Marking as failed.")
                return PaymentFailedStatus(False)

            r.raise_for_status()
            return PaymentPendingStatus()

        except httpx.HTTPStatusError as e:
            logger.warning(
                f"HTTPStatusError in get_invoice_status for checking_id {checking_id} "
                f"on URL {e.request.url}: {e.response.status_code} - {e.response.text}"
            )
            # Default to Pending to allow retries by paid_invoices_stream.
            return PaymentPendingStatus()
        except Exception as e:
            logger.warning(e)
            return PaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> PaymentStatus:
        quote_id = self.pending_payments.get(checking_id)

        try:
            # Attempt 1: Use quote_id if available (from in-memory store)
            if quote_id:
                status = await self._get_payment_status_by_quote_id(
                    checking_id, quote_id
                )
                if status:
                    return status
        except Exception as e:
            logger.warning(e)
            logger.debug(f"Error while fetching payment by quote id {checking_id}.")

        try:
            # Attempt 2: Fallback - Use paymentId (checking_id) directly.
            return await self._get_payment_status_by_checking_id(checking_id)
        except Exception as e:
            logger.warning(e)
            logger.debug(f"Error while fetching payment {checking_id}.")
            return PaymentPendingStatus()

    async def get_invoices(
        self,
        filters: str | None = None,
        orderby: str | None = None,
        skip: int | None = None,
        top: int | None = None,
    ) -> dict[str, Any]:
        try:
            params: dict[str, Any] = {}
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
            r.raise_for_status()
            return r.json()
        except Exception:
            logger.warning("Error in get_invoices()")
            return {"error": "unable to fetch invoices"}

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        """
        Poll Strike for invoice settlement while respecting the documented API limits.

        Uses dynamic adjustment of polling frequency based on activity.
        """
        min_poll, max_poll = 0.2, 3  # Increase polling frequency (was 1, 15)
        # 1,000 requests / 10 minutes = ~100 requests/minute.
        rate_limit = 250
        sleep_s = min_poll
        # Main loop for polling invoices.
        self._running = True

        while self._running and settings.lnbits_running:
            loop_start = time.time()
            had_activity = False

            req_budget = max(
                1, rate_limit * sleep_s // 60
            )  # Calculate request budget based on sleep time.
            batch = list(self.pending_invoices)[: int(req_budget)]
            processed = 0
            if batch:
                statuses = await self._get_invoices_status_batch(batch)
                processed = 1
                for inv, status in statuses.items():
                    if status.success or status.failed:
                        self.pending_invoices.remove(inv)
                        self._persist_pending()
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

    # --------------------------------------------------------------------- #
    # low-level request helpers                                             #
    # --------------------------------------------------------------------- #

    def _persist_pending(self):
        try:
            with open(self.state_path, "w") as f:
                json.dump(self.pending_invoices, f)
        except Exception as e:
            logger.warning(f"Could not persist pending invoices: {e}")

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
            return await self.client.request(method, path, **kw)

    # Typed wrappers - so call-sites stay tidy.
    async def _get(self, path: str, **kw) -> httpx.Response:  # GET request.
        return await self._req("GET", path, **kw)

    async def _post(self, path: str, **kw) -> httpx.Response:
        return await self._req("POST", path, **kw)

    async def _patch(self, path: str, **kw) -> httpx.Response:
        return await self._req("PATCH", path, **kw)

    async def _create_payment_quote(self, bolt11: str) -> tuple[str | None, str | None]:
        """Create a payment quote and return (quote_id, error_message)."""
        try:
            q = await self._post(
                "/payment-quotes/lightning",
                json={"lnInvoice": bolt11},
            )
            q.raise_for_status()
        except httpx.HTTPStatusError as quote_exc:
            logger.warning(f"Strike: Failed to create payment quote: {quote_exc}")
            logger.warning(
                f"Response: {quote_exc.response.status_code} - "
                f"{quote_exc.response.text}"
            )
            error_msg = (
                f"Strike: Failed to create quote "
                f"(HTTP {quote_exc.response.status_code})"
            )
            return None, error_msg

        quote_data = q.json()
        quote_id = quote_data.get("paymentQuoteId")
        if not quote_id:
            logger.warning(
                f"Strike: missing paymentQuoteId in quote response: {quote_data}"
            )
            return None, "Strike: missing payment quote Id"

        return quote_id, None

    async def _execute_payment_quote(
        self, quote_id: str
    ) -> tuple[dict | None, str | None]:
        """Execute a payment quote and return (response_data, error_message)."""
        try:
            e = await self._patch(f"/payment-quotes/{quote_id}/execute")
            e.raise_for_status()
        except httpx.HTTPStatusError as exec_exc:
            logger.warning(
                f"Strike: Failed to execute payment quote {quote_id}: {exec_exc}"
            )
            logger.warning(
                f"Response: {exec_exc.response.status_code} - "
                f"{exec_exc.response.text}"
            )
            error_msg = (
                f"Strike: Failed to execute quote "
                f"(HTTP {exec_exc.response.status_code})"
            )
            return None, error_msg

        data = e.json() if e.content else {}
        payment_id = data.get("paymentId")
        if not payment_id:
            logger.warning(f"Strike: missing paymentId in response: {data}")
            return None, "Strike: missing paymentId in response"

        return data, None

    def _parse_payment_fee(self, data: dict, payment_id: str) -> int:
        """Parse payment fee from response data and return fee in millisatoshis."""
        lightning_data = data.get("lightning", {})
        fee_obj = lightning_data.get("networkFee") or data.get("totalFee") or {}
        fee_msat = 0
        try:
            fee_amount = fee_obj.get("amount")
            if fee_amount is not None:
                fee_btc = Decimal(str(fee_amount))
                fee_msat = int(fee_btc * Decimal("1e11"))
        except Exception as fee_exc:
            logger.warning(f"Error parsing fee for payment {payment_id}: {fee_exc}")
        return fee_msat

    def _extract_preimage(self, data: dict) -> str | None:
        """Extract preimage from payment response data."""
        lightning_data = data.get("lightning", {})
        return (
            lightning_data.get("preimage")
            or lightning_data.get("preImage")
            or data.get("preimage")
            or data.get("preImage")
        )

    async def _get_invoices_status_batch(
        self, invoice_ids: list[str]
    ) -> dict[str, PaymentStatus]:
        out: dict[str, PaymentStatus] = {}
        if not invoice_ids:
            return out
        ids_list = ",".join(f"'{i}'" for i in invoice_ids)
        filter_expr = f"receiveRequestId in ({ids_list})"
        params = {"$filter": filter_expr, "$top": len(invoice_ids)}
        r = await self._get("/receive-requests/receives", params=params)
        r.raise_for_status()
        items = r.json().get("items") or r.json().get("value") or []
        completed = {item.get("receiveRequestId") for item in items}
        for inv in invoice_ids:
            out[inv] = (
                PaymentSuccessStatus(fee_msat=0)
                if inv in completed
                else PaymentPendingStatus()
            )
        return out

    # ------------------------------------------------------------------ #
    # misc Strike helpers                                                #
    # ------------------------------------------------------------------ #

    async def _get_payment_status_by_quote_id(
        self, checking_id: str, quote_id: str
    ) -> PaymentStatus | None:
        resp = await self._get(f"/payment-quotes/{quote_id}")
        resp.raise_for_status()

        data = resp.json()
        state = data.get("state", "").upper()

        # Extract preimage from lightning object (new API structure)
        lightning_data = data.get("lightning", {})
        preimage = (
            lightning_data.get("preimage")
            or lightning_data.get("preImage")
            or data.get("preimage")
            or data.get("preImage")
        )

        fee_msat = 0
        # Updated API structure (Aug 26, 2024): fee is now in lightning.networkFee
        fee_obj = lightning_data.get("networkFee") or data.get("totalFee")
        if fee_obj and fee_obj.get("amount") and fee_obj.get("currency"):
            amount_str = fee_obj.get("amount")
            currency_str = fee_obj.get("currency").upper()
            try:
                if currency_str == "BTC":
                    fee_btc_decimal = Decimal(amount_str)
                    fee_msat = int(fee_btc_decimal * Decimal("1e11"))
                elif currency_str == "SAT":
                    fee_sat_decimal = Decimal(amount_str)
                    fee_msat = int(fee_sat_decimal * 1000)
            except Exception as e:
                logger.warning(e)
                logger.warning(
                    f"Fee parse error. Quote: '{quote_id}'. "
                    f"Payment '{checking_id}'."
                )
                fee_msat = 0

        if state in {"SUCCEEDED", "COMPLETED"}:
            self.pending_payments.pop(checking_id, None)
            return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)
        if state == "FAILED":
            self.pending_payments.pop(checking_id, None)
            return PaymentFailedStatus()

        return None

    async def _get_payment_status_by_checking_id(  # noqa: C901
        self, checking_id: str
    ) -> PaymentStatus:
        r_payment = await self._get(f"/payments/{checking_id}")

        if r_payment.status_code == 200:
            data = r_payment.json()
            state = data.get("state", "").upper()

            # Extract data from lightning object (new API structure)
            lightning_data = data.get("lightning", {})
            preimage = (
                lightning_data.get("preimage")
                or lightning_data.get("preImage")
                or data.get("preimage")
                or data.get("preImage")
            )

            # Extract fee from new API structure
            fee_obj = lightning_data.get("networkFee") or data.get("totalFee")
            fee_msat = 0
            if fee_obj and fee_obj.get("amount"):
                try:
                    fee_btc = Decimal(fee_obj.get("amount", "0"))
                    currency = fee_obj.get("currency", "BTC").upper()
                    if currency == "BTC":
                        fee_msat = int(fee_btc * Decimal("1e11"))
                    elif currency == "SAT":
                        fee_msat = int(fee_btc * 1000)
                except Exception as e:
                    logger.warning(f"Error parsing fee for payment {checking_id}: {e}")
                    fee_msat = 0

            if state in {"SUCCEEDED", "COMPLETED"}:
                self.pending_payments.pop(checking_id, None)
                return PaymentSuccessStatus(fee_msat=fee_msat, preimage=preimage)
            if state == "FAILED":
                self.pending_payments.pop(checking_id, None)
                return PaymentFailedStatus()

            return PaymentPendingStatus()

        if r_payment.status_code == 400:
            try:
                error_data = r_payment.json()
                # Check for Strike's specific validation
                # error structure for paymentId format
                if error_data.get("data", {}).get("code") == "INVALID_DATA":
                    validation_errors = error_data.get("data", {}).get(
                        "validationErrors", {}
                    )
                    if "paymentId" in validation_errors:
                        for err_detail in validation_errors["paymentId"]:
                            is_invalid = err_detail.get(
                                "code"
                            ) == "INVALID_DATA" and "is not valid." in err_detail.get(
                                "message", ""
                            )
                            if not is_invalid:
                                continue
                            logger.warning(
                                f"Payment '{checking_id}' not a valid Strike payment. "
                                f"Marked as failed. Response: {r_payment.text}"
                            )
                            self.pending_payments.pop(checking_id, None)
                            return PaymentFailedStatus()
            except Exception as e:
                logger.warning(e)

            return PaymentPendingStatus()

        if r_payment.status_code == 404:
            logger.warning(f"Payment {checking_id} not found. Marking as failed.")
            self.pending_payments.pop(checking_id, None)
            return PaymentFailedStatus()

        logger.debug(
            f"Error fetching payment {checking_id} directly: "
            f"{r_payment.status_code} - {r_payment.text}"
        )
        return PaymentPendingStatus()
