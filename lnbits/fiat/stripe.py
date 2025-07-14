import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

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
        self, only_check_settings: Optional[bool] = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            r = await self.client.get(url="/v1/balance", timeout=15)
            r.raise_for_status()
            data = r.json()

            available_balance = data.get("available", [{}])[0].get("amount", 0)
            # pending_balance = data.get("pending", {}).get("amount", 0)

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
        **kwargs,
    ) -> FiatInvoiceResponse:
        amount_cents = int(amount * 100)
        form_data = [
            ("mode", "payment"),
            (
                "success_url",
                settings.stripe_payment_success_url or "https://lnbits.com",
            ),
            ("metadata[payment_hash]", payment_hash),
            ("line_items[0][price_data][currency]", currency.lower()),
            ("line_items[0][price_data][product_data][name]", memo or "LNbits Invoice"),
            ("line_items[0][price_data][unit_amount]", amount_cents),
            ("line_items[0][quantity]", "1"),
        ]
        encoded_data = urlencode(form_data)

        try:
            headers = self.headers.copy()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            r = await self.client.post(
                url="/v1/checkout/sessions", headers=headers, content=encoded_data
            )
            r.raise_for_status()
            data = r.json()

            session_id = data.get("id")
            if not session_id:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: 'missing session id'"
                )
            payment_request = data.get("url")
            if not payment_request:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: 'missing payment URL'"
                )

            return FiatInvoiceResponse(
                ok=True, checking_id=session_id, payment_request=payment_request
            )
        except json.JSONDecodeError:
            return FiatInvoiceResponse(
                ok=False, error_message="Server error: 'invalid json response'"
            )
        except Exception as exc:
            logger.warning(exc)
            return FiatInvoiceResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Stripe does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            r = await self.client.get(
                url=f"/v1/checkout/sessions/{checking_id}",
            )
            r.raise_for_status()

            data = r.json()
            payment_status = data.get("payment_status")
            if not payment_status:
                return FiatPaymentPendingStatus()
            if payment_status == "paid":
                # todo: handle fee
                return FiatPaymentSuccessStatus()

            expires_at = data.get("expires_at")
            _24_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            if expires_at and expires_at < _24_hours_ago.timestamp():
                # be defensive: add a 24 hour buffer
                return FiatPaymentFailedStatus()

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
