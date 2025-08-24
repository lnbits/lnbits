import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Dict, Literal, Optional
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
    class Config: extra = "ignore"
    capture_method: Literal["automatic", "manual"] = "automatic"
    metadata: Dict[str, str] = Field(default_factory=dict)

class StripeCheckoutOptions(BaseModel):
    class Config: extra = "ignore"
    success_url: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)
    line_item_name: Optional[str] = None

class StripeCreateInvoiceOptions(BaseModel):
    class Config: extra = "ignore"
    fiat_method: FiatMethod = "checkout"
    terminal: Optional[StripeTerminalOptions] = None
    checkout: Optional[StripeCheckoutOptions] = None

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

            # Stripe returns lists like {"available": [{"amount": 123, "currency":"gbp"}, ...]}
            available = data.get("available") or []
            available_balance = 0
            if available and isinstance(available, list):
                # If multiple currencies exist, you could sum/filter here; keeping first for simplicity
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
        memo: Optional[str] = None,
        extra: Optional[dict] = None,
        **kwargs,
    ) -> FiatInvoiceResponse:
        amount_cents = int(amount * 100)

        # Validate/normalize provider-specific kwargs up front
        raw_opts = extra or {}
        try:
            opts = StripeCreateInvoiceOptions.parse_obj(raw_opts)  # pydantic v1
        except ValidationError as e:
            logger.warning(f"Invalid Stripe options: {e}")
            return FiatInvoiceResponse(ok=False, error_message=f"Invalid Stripe options: {e}")


        fiat_method: FiatMethod = opts.fiat_method

        if fiat_method == "checkout":
            # Apply defaults for checkout options
            co = opts.checkout or StripeCheckoutOptions()
            success_url = (
                co.success_url
                or settings.stripe_payment_success_url
                or "https://lnbits.com"
            )
            line_item_name = co.line_item_name or memo or "LNbits Invoice"

            form_data = [
                ("mode", "payment"),
                ("success_url", success_url),
                ("metadata[payment_hash]", payment_hash),
                ("line_items[0][price_data][currency]", currency.lower()),
                ("line_items[0][price_data][product_data][name]", line_item_name),
                ("line_items[0][price_data][unit_amount]", amount_cents),
                ("line_items[0][quantity]", "1"),
            ]

            # Extra metadata, if given
            if co.metadata:
                for k, v in co.metadata.items():
                    form_data.append((f"metadata[{k}]", str(v)))

            encoded_data = urlencode(form_data)
            try:
                headers = {**self.headers, "Content-Type": "application/x-www-form-urlencoded"}
                r = await self.client.post("/v1/checkout/sessions", headers=headers, content=encoded_data)
                r.raise_for_status()
                data = r.json()

                session_id = data.get("id")
                url = data.get("url")
                if not session_id or not url:
                    return FiatInvoiceResponse(ok=False, error_message="Server error: missing id or url")

                # checking_id is the Stripe object id to poll later
                return FiatInvoiceResponse(ok=True, checking_id=session_id, payment_request=url)

            except json.JSONDecodeError:
                return FiatInvoiceResponse(ok=False, error_message="Server error: invalid json response")
            except Exception as exc:
                logger.warning(exc)
                return FiatInvoiceResponse(ok=False, error_message=f"Unable to connect to {self.endpoint}.")

        elif fiat_method == "terminal":
            # Apply defaults for terminal options
            term = opts.terminal or StripeTerminalOptions()
            try:
                data = {
                    "amount": amount_cents,
                    "currency": currency.lower(),
                    "payment_method_types[]": "card_present",
                    "capture_method": term.capture_method,
                    "metadata[payment_hash]": payment_hash,
                    "metadata[source]": "lnbits"  # optional, but useful to identify
                }
                if term.metadata:
                    for k, v in term.metadata.items():
                        data[f"metadata[{k}]"] = str(v)

                r = await self.client.post("/v1/payment_intents", data=data)
                r.raise_for_status()
                pi = r.json()

                pi_id = pi.get("id")
                client_secret = pi.get("client_secret")
                if not pi_id or not client_secret:
                    return FiatInvoiceResponse(ok=False, error_message="Server error: missing PaymentIntent or client_secret")

                # For Terminal, return the client_secret as payment_request for the SDK flow.
                return FiatInvoiceResponse(ok=True, checking_id=pi_id, payment_request=client_secret)

            except json.JSONDecodeError:
                return FiatInvoiceResponse(ok=False, error_message="Server error: invalid json response")
            except Exception as exc:
                logger.warning(exc)
                return FiatInvoiceResponse(ok=False, error_message=f"Unable to connect to {self.endpoint}.")

        else:
            return FiatInvoiceResponse(ok=False, error_message=f"Unsupported fiat_method: {fiat_method}")

    async def create_terminal_connection_token(self, location_id: Optional[str] = None) -> dict:
        data = {}
        if location_id:
            data["location"] = location_id
        r = await self.client.post("/v1/terminal/connection_tokens", data=data)
        r.raise_for_status()
        return r.json()

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Stripe does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            if checking_id.startswith("cs_"):
                # Checkout flow
                r = await self.client.get(f"/v1/checkout/sessions/{checking_id}")
                r.raise_for_status()
                data = r.json()

                payment_status = data.get("payment_status")
                if payment_status == "paid":
                    return FiatPaymentSuccessStatus()

                expires_at = data.get("expires_at")
                _24h_ago = datetime.now(timezone.utc) - timedelta(hours=24)
                if expires_at and float(expires_at) < _24h_ago.timestamp():
                    return FiatPaymentFailedStatus()

                return FiatPaymentPendingStatus()

            elif checking_id.startswith("pi_"):
                # Terminal flow
                r = await self.client.get(f"/v1/payment_intents/{checking_id}")
                r.raise_for_status()
                pi = r.json()
                status = pi.get("status")

                # Common states:
                #   requires_payment_method, requires_confirmation,
                #   processing, requires_capture (if manual), succeeded, canceled
                if status == "succeeded":
                    return FiatPaymentSuccessStatus()
                if status in ("canceled",):
                    return FiatPaymentFailedStatus()

                # If manual capture is used, "requires_capture" should remain pending here
                return FiatPaymentPendingStatus()

            else:
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

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [str(settings.stripe_api_endpoint), str(settings.stripe_api_secret_key)]
        )
