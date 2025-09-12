import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlencode

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from lnbits.helpers import normalize_endpoint
from lnbits.settings import settings

from .base import (
    FiatInvoiceResponse,
    FiatPaymentFailedStatus,
    FiatPaymentPendingStatus,
    FiatPaymentResponse,
    FiatPaymentStatus,
    FiatPaymentSuccessStatus,
    FiatProvider,
    FiatStatusResponse,
)

FiatMethod = Literal["checkout", "terminal"]


class StripeTerminalOptions(BaseModel):
    class Config:
        extra = "ignore"

    capture_method: Literal["automatic", "manual"] = "automatic"
    metadata: dict[str, str] = Field(default_factory=dict)


class StripeCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    line_item_name: str | None = None


class StripeCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    fiat_method: FiatMethod = "checkout"
    terminal: StripeTerminalOptions | None = None
    checkout: StripeCheckoutOptions | None = None


class StripeWallet(FiatProvider):
    """https://docs.stripe.com/api"""

    def __init__(self):
        logger.debug("Initializing StripeWallet")
        self._settings_fields = self._settings_connection_fields()
        if not settings.stripe_api_endpoint:
            raise ValueError("Cannot initialize StripeWallet: missing endpoint.")
        if not settings.stripe_api_secret_key:
            raise ValueError("Cannot initialize StripeWallet: missing API secret key.")

        self.endpoint = normalize_endpoint(settings.stripe_api_endpoint)
        self.headers = {
            "Authorization": f"Bearer {settings.stripe_api_secret_key}",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)
        logger.info("StripeWallet initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing stripe wallet connection: {e}")

    async def status(
        self, only_check_settings: bool | None = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            r = await self.client.get(url="/v1/balance", timeout=15)
            r.raise_for_status()
            data = r.json()

            available = data.get("available") or []
            available_balance = 0
            if available and isinstance(available, list):
                available_balance = int(available[0].get("amount", 0))

            return FiatStatusResponse(balance=available_balance)
        except json.JSONDecodeError:
            return FiatStatusResponse("Server error: 'invalid json response'", 0)
        except Exception as exc:
            logger.warning(exc)
            return FiatStatusResponse(f"Unable to connect to {self.endpoint}.", 0)

    async def create_invoice(
        self,
        amount: float,
        payment_hash: str,
        currency: str,
        memo: str | None = None,
        extra: dict[str, Any] | None = None,
        **kwargs,
    ) -> FiatInvoiceResponse:
        amount_cents = int(amount * 100)
        opts = self._parse_create_opts(extra or {})
        if not opts:
            return FiatInvoiceResponse(ok=False, error_message="Invalid Stripe options")

        if opts.fiat_method == "checkout":
            return await self._create_checkout_invoice(
                amount_cents, currency, payment_hash, memo, opts
            )
        if opts.fiat_method == "terminal":
            return await self._create_terminal_invoice(
                amount_cents, currency, payment_hash, opts
            )

        return FiatInvoiceResponse(
            ok=False, error_message=f"Unsupported fiat_method: {opts.fiat_method}"
        )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Stripe does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            stripe_id = self._normalize_stripe_id(checking_id)

            if stripe_id.startswith("cs_"):
                r = await self.client.get(f"/v1/checkout/sessions/{stripe_id}")
                r.raise_for_status()
                return self._status_from_checkout_session(r.json())

            if stripe_id.startswith("pi_"):
                r = await self.client.get(f"/v1/payment_intents/{stripe_id}")
                r.raise_for_status()
                return self._status_from_payment_intent(r.json())

            logger.debug(f"Unknown Stripe id prefix: {checking_id}")
            return FiatPaymentPendingStatus()

        except Exception as exc:
            logger.debug(f"Error getting invoice status: {exc}")
            return FiatPaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> FiatPaymentStatus:
        raise NotImplementedError("Stripe does not support outgoing payments.")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        logger.warning(
            "Stripe does not support paid invoices stream. Use webhooks instead."
        )
        mock_queue: asyncio.Queue[str] = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await mock_queue.get()
            yield value

    async def create_terminal_connection_token(self) -> dict:
        r = await self.client.post("/v1/terminal/connection_tokens")
        r.raise_for_status()
        return r.json()

    async def _create_checkout_invoice(
        self,
        amount_cents: int,
        currency: str,
        payment_hash: str,
        memo: str | None,
        opts: StripeCreateInvoiceOptions,
    ) -> FiatInvoiceResponse:
        co = opts.checkout or StripeCheckoutOptions()
        success_url = (
            co.success_url
            or settings.stripe_payment_success_url
            or "https://lnbits.com"
        )
        line_item_name = co.line_item_name or memo or "LNbits Invoice"

        form_data: list[tuple[str, str]] = [
            ("mode", "payment"),
            ("success_url", success_url),
            ("metadata[payment_hash]", payment_hash),
            ("line_items[0][price_data][currency]", currency.lower()),
            ("line_items[0][price_data][product_data][name]", line_item_name),
            ("line_items[0][price_data][unit_amount]", str(amount_cents)),
            ("line_items[0][quantity]", "1"),
        ]
        form_data += self._encode_metadata("metadata", co.metadata)

        try:
            r = await self.client.post(
                "/v1/checkout/sessions",
                headers=self._build_headers_form(),
                content=urlencode(form_data),
            )
            r.raise_for_status()
            data = r.json()
            session_id, url = data.get("id"), data.get("url")
            if not session_id or not url:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: missing id or url"
                )
            return FiatInvoiceResponse(
                ok=True, checking_id=session_id, payment_request=url
            )
        except json.JSONDecodeError:
            return FiatInvoiceResponse(
                ok=False, error_message="Server error: invalid json response"
            )
        except Exception as exc:
            logger.warning(exc)
            return FiatInvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def _create_terminal_invoice(
        self,
        amount_cents: int,
        currency: str,
        payment_hash: str,
        opts: StripeCreateInvoiceOptions,
    ) -> FiatInvoiceResponse:
        term = opts.terminal or StripeTerminalOptions()
        data: dict[str, str] = {
            "amount": str(amount_cents),
            "currency": currency.lower(),
            "payment_method_types[]": "card_present",
            "capture_method": term.capture_method,
            "metadata[payment_hash]": payment_hash,
            "metadata[source]": "lnbits",
        }
        for k, v in (term.metadata or {}).items():
            data[f"metadata[{k}]"] = str(v)

        try:
            r = await self.client.post("/v1/payment_intents", data=data)
            r.raise_for_status()
            pi = r.json()
            pi_id, client_secret = pi.get("id"), pi.get("client_secret")
            if not pi_id or not client_secret:
                return FiatInvoiceResponse(
                    ok=False,
                    error_message="Error: missing PaymentIntent or client_secret",
                )
            return FiatInvoiceResponse(
                ok=True, checking_id=pi_id, payment_request=client_secret
            )
        except json.JSONDecodeError:
            return FiatInvoiceResponse(
                ok=False, error_message="Error: invalid json response"
            )
        except Exception as exc:
            logger.warning(exc)
            return FiatInvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    def _normalize_stripe_id(self, checking_id: str) -> str:
        """Remove our internal prefix so Stripe sees a real id."""
        return (
            checking_id.replace("fiat_stripe_", "", 1)
            if checking_id.startswith("fiat_stripe_")
            else checking_id
        )

    def _status_from_checkout_session(self, data: dict) -> FiatPaymentStatus:
        """Map a Checkout Session to LNbits fiat status."""
        if data.get("payment_status") == "paid":
            return FiatPaymentSuccessStatus()

        # Consider an expired session a fail (existing 24h rule).
        expires_at = data.get("expires_at")
        _24h_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        if expires_at and float(expires_at) < _24h_ago.timestamp():
            return FiatPaymentFailedStatus()

        return FiatPaymentPendingStatus()

    def _status_from_payment_intent(self, pi: dict) -> FiatPaymentStatus:
        """Map a PaymentIntent to LNbits fiat status (card_present friendly)."""
        status = pi.get("status")

        if status == "succeeded":
            return FiatPaymentSuccessStatus()

        if status in ("canceled", "payment_failed"):
            return FiatPaymentFailedStatus()

        if status == "requires_payment_method":
            if pi.get("last_payment_error"):
                return FiatPaymentFailedStatus()

            now_ts = datetime.now(timezone.utc).timestamp()
            created_ts = float(pi.get("created") or now_ts)
            is_stale = (now_ts - created_ts) > 300
            if is_stale:
                return FiatPaymentFailedStatus()

        return FiatPaymentPendingStatus()

    def _build_headers_form(self) -> dict[str, str]:
        return {**self.headers, "Content-Type": "application/x-www-form-urlencoded"}

    def _encode_metadata(
        self, prefix: str, md: dict[str, Any]
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for k, v in (md or {}).items():
            out.append((f"{prefix}[{k}]", str(v)))
        return out

    def _parse_create_opts(
        self, raw_opts: dict[str, Any]
    ) -> StripeCreateInvoiceOptions | None:
        try:
            return StripeCreateInvoiceOptions.parse_obj(raw_opts)
        except ValidationError as e:
            logger.warning(f"Invalid Stripe options: {e}")
            return None

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [str(settings.stripe_api_endpoint), str(settings.stripe_api_secret_key)]
        )
