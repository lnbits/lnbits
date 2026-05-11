import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Literal

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
    FiatSubscriptionPaymentOptions,
    FiatSubscriptionResponse,
)

FiatMethod = Literal["checkout"]


class SquareCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    line_item_name: str | None = None


class SquareCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    fiat_method: FiatMethod = "checkout"
    checkout: SquareCheckoutOptions | None = None


class SquareWallet(FiatProvider):
    """https://developer.squareup.com/reference/square"""

    def __init__(self):
        logger.debug("Initializing SquareWallet")
        self._settings_fields = self._settings_connection_fields()
        if not settings.square_api_endpoint:
            raise ValueError("Cannot initialize SquareWallet: missing endpoint.")
        if not settings.square_access_token:
            raise ValueError("Cannot initialize SquareWallet: missing access token.")
        if not settings.square_location_id:
            raise ValueError("Cannot initialize SquareWallet: missing location ID.")

        self.endpoint = normalize_endpoint(settings.square_api_endpoint)
        self.location_id = settings.square_location_id
        self.headers = {
            "Authorization": f"Bearer {settings.square_access_token}",
            "Square-Version": settings.square_api_version,
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)
        logger.info("SquareWallet initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing Square wallet connection: {e}")

    async def status(
        self, only_check_settings: bool | None = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            r = await self.client.get(f"/v2/locations/{self.location_id}", timeout=15)
            r.raise_for_status()
            _ = r.json()
            return FiatStatusResponse(balance=0)
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
        opts = self._parse_create_opts(extra or {})
        if not opts:
            return FiatInvoiceResponse(ok=False, error_message="Invalid Square options")

        amount_cents = int(amount * 100)
        co = opts.checkout or SquareCheckoutOptions()
        success_url = (
            co.success_url
            or settings.square_payment_success_url
            or "https://lnbits.com"
        )
        line_item_name = (co.line_item_name or memo or "LNbits Invoice")[:255]
        metadata = {
            **co.metadata,
            "payment_hash": payment_hash,
            "alan_action": "invoice",
        }

        payload = {
            "idempotency_key": payment_hash,
            "order": {
                "location_id": self.location_id,
                "metadata": metadata,
                "line_items": [
                    {
                        "name": line_item_name,
                        "quantity": "1",
                        "base_price_money": {
                            "amount": amount_cents,
                            "currency": currency.upper(),
                        },
                    }
                ],
            },
            "checkout_options": {"redirect_url": success_url},
        }
        if memo:
            payload["payment_note"] = memo[:500]

        try:
            r = await self.client.post(
                "/v2/online-checkout/payment-links", json=payload
            )
            r.raise_for_status()
            data = r.json()
            payment_link = data.get("payment_link") or {}
            order_id = payment_link.get("order_id")
            url = payment_link.get("url")
            if not order_id or not url:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: missing order id or url"
                )
            return FiatInvoiceResponse(
                ok=True,
                checking_id=f"order_{order_id}",
                payment_request=url,
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

    async def create_subscription(
        self,
        subscription_id: str,
        quantity: int,
        payment_options: FiatSubscriptionPaymentOptions,
        **kwargs,
    ) -> FiatSubscriptionResponse:
        return FiatSubscriptionResponse(
            ok=False, error_message="Square subscriptions are not supported."
        )

    async def cancel_subscription(
        self,
        subscription_id: str,
        correlation_id: str,
        **kwargs,
    ) -> FiatSubscriptionResponse:
        return FiatSubscriptionResponse(
            ok=False, error_message="Square subscriptions are not supported."
        )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Square does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            square_id = self._normalize_square_id(checking_id)
            if square_id.startswith("payment_"):
                payment_id = square_id.replace("payment_", "", 1)
                return await self._get_payment_status(payment_id)

            order_id = (
                square_id.replace("order_", "", 1)
                if square_id.startswith("order_")
                else square_id
            )
            return await self._get_order_status(order_id)
        except Exception as exc:
            logger.debug(f"Error getting Square invoice status: {exc}")
            return FiatPaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> FiatPaymentStatus:
        raise NotImplementedError("Square does not support outgoing payments.")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        logger.warning(
            "Square does not support paid invoices stream. Use webhooks instead."
        )
        mock_queue: asyncio.Queue[str] = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await mock_queue.get()
            yield value

    async def _get_order_status(self, order_id: str) -> FiatPaymentStatus:
        r = await self.client.get(f"/v2/orders/{order_id}")
        r.raise_for_status()
        order = r.json().get("order") or {}
        tenders = order.get("tenders") or []
        payment_id = None
        for tender in tenders:
            payment_id = tender.get("payment_id")
            if payment_id:
                break

        if payment_id:
            return await self._get_payment_status(payment_id)

        if (order.get("state") or "").upper() == "CANCELED":
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    async def _get_payment_status(self, payment_id: str) -> FiatPaymentStatus:
        r = await self.client.get(f"/v2/payments/{payment_id}")
        r.raise_for_status()
        return self._status_from_payment(r.json().get("payment") or {})

    def _status_from_payment(self, payment: dict[str, Any]) -> FiatPaymentStatus:
        status = (payment.get("status") or "").upper()
        if status == "COMPLETED":
            return FiatPaymentSuccessStatus()
        if status in ["CANCELED", "FAILED"]:
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    def _normalize_square_id(self, checking_id: str) -> str:
        return (
            checking_id.replace("fiat_square_", "", 1)
            if checking_id.startswith("fiat_square_")
            else checking_id
        )

    def _parse_create_opts(
        self, raw_opts: dict[str, Any]
    ) -> SquareCreateInvoiceOptions | None:
        try:
            return SquareCreateInvoiceOptions.parse_obj(raw_opts)
        except ValidationError as e:
            logger.warning(f"Invalid Square options: {e}")
            return None

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [
                str(settings.square_api_endpoint),
                str(settings.square_access_token),
                str(settings.square_location_id),
                str(settings.square_api_version),
            ]
        )
