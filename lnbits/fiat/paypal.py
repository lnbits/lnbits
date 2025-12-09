import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from lnbits.helpers import normalize_endpoint, urlsafe_short_hash
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


class PayPalCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    cancel_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PayPalCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    checkout: PayPalCheckoutOptions | None = None


class PayPalWallet(FiatProvider):
    """https://developer.paypal.com/api/rest/"""

    def __init__(self):
        logger.debug("Initializing PayPalWallet")
        self._settings_fields = self._settings_connection_fields()
        if not settings.paypal_api_endpoint:
            raise ValueError("Cannot initialize PayPalWallet: missing endpoint.")
        if not settings.paypal_client_id:
            raise ValueError("Cannot initialize PayPalWallet: missing client id.")
        if not settings.paypal_client_secret:
            raise ValueError("Cannot initialize PayPalWallet: missing client secret.")

        self.endpoint = normalize_endpoint(settings.paypal_api_endpoint)
        self.headers = {
            "User-Agent": f"PayPal Alan:{settings.version}",
        }
        self._access_token: str | None = None
        self._token_expires_at: float = 0
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)
        logger.info("PayPalWallet initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing PayPal wallet connection: {e}")

    async def status(
        self, only_check_settings: bool | None = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            await self._ensure_access_token()
            return FiatStatusResponse(balance=0)
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
        if opts is None:
            return FiatInvoiceResponse(ok=False, error_message="Invalid PayPal options")

        try:
            await self._ensure_access_token()
        except Exception as exc:
            logger.warning(exc)
            return FiatInvoiceResponse(
                ok=False, error_message="Unable to authenticate."
            )

        co = opts.checkout or PayPalCheckoutOptions()
        success_url = (
            co.success_url
            or settings.paypal_payment_success_url
            or "https://lnbits.com"
        )
        cancel_url = co.cancel_url or success_url

        order_data = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": f"{amount:.2f}",
                    },
                    "custom_id": payment_hash[:127],  # PayPal limit
                    "invoice_id": payment_hash[:127],
                    "description": memo or "LNbits Invoice",
                }
            ],
            "application_context": {
                "return_url": success_url,
                "cancel_url": cancel_url,
                "shipping_preference": "NO_SHIPPING",
                "user_action": "PAY_NOW",
            },
        }

        try:
            r = await self.client.post(
                "/v2/checkout/orders", json=order_data, headers=self._auth_headers()
            )
            r.raise_for_status()
            data = r.json()
            order_id = data.get("id")
            approval_url = self._get_approval_url(data.get("links") or [])
            if not order_id or not approval_url:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: missing id or approval url"
                )

            return FiatInvoiceResponse(
                ok=True,
                checking_id=f"fiat_paypal_{order_id}",
                payment_request=approval_url,
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
        success_url = (
            payment_options.success_url
            or settings.paypal_payment_success_url
            or "https://lnbits.com"
        )

        if not payment_options.subscription_request_id:
            payment_options.subscription_request_id = urlsafe_short_hash()
        payment_options.extra = payment_options.extra or {}
        payment_options.extra["subscription_request_id"] = (
            payment_options.subscription_request_id
        )

        try:
            await self._ensure_access_token()
            payload = {
                "plan_id": subscription_id,
                "quantity": str(quantity),
                "custom_id": self._serialize_metadata(payment_options),
                "application_context": {
                    "return_url": success_url,
                    "cancel_url": success_url,
                },
            }
            r = await self.client.post(
                "/v1/billing/subscriptions",
                json=payload,
                headers=self._auth_headers(),
            )
            r.raise_for_status()
            data = r.json()
            approval_url = self._get_approval_url(data.get("links") or [])
            if not approval_url:
                return FiatSubscriptionResponse(
                    ok=False, error_message="Server error: missing approval url"
                )

            return FiatSubscriptionResponse(
                ok=True,
                checkout_session_url=approval_url,
                subscription_request_id=payment_options.subscription_request_id,
            )
        except Exception as exc:
            logger.warning(exc)
            return FiatSubscriptionResponse(
                ok=False, error_message=f"Unable to connect to {self.endpoint}."
            )

    async def cancel_subscription(
        self,
        subscription_id: str,
        correlation_id: str,
        **kwargs,
    ) -> FiatSubscriptionResponse:
        try:
            await self._ensure_access_token()
            r = await self.client.post(
                f"/v1/billing/subscriptions/{subscription_id}/cancel",
                json={"reason": f"Cancelled by {correlation_id}"},
                headers=self._auth_headers(),
            )
            r.raise_for_status()
            return FiatSubscriptionResponse(ok=True)
        except Exception as exc:
            logger.warning(exc)
            return FiatSubscriptionResponse(
                ok=False, error_message="Unable to cancel subscription."
            )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("PayPal does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            await self._ensure_access_token()
            order_id = self._normalize_paypal_id(checking_id)
            r = await self.client.get(
                f"/v2/checkout/orders/{order_id}", headers=self._auth_headers()
            )
            r.raise_for_status()
            return self._status_from_order(r.json())
        except Exception as exc:
            logger.debug(f"Error getting PayPal order status: {exc}")
            return FiatPaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> FiatPaymentStatus:
        raise NotImplementedError("PayPal does not support outgoing payments.")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        logger.warning(
            "PayPal does not support paid invoices stream. Use webhooks instead."
        )
        mock_queue: asyncio.Queue[str] = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await mock_queue.get()
            yield value

    def _status_from_order(self, order: dict[str, Any]) -> FiatPaymentStatus:
        status = (order.get("status") or "").upper()
        if status in ["COMPLETED", "APPROVED"]:
            return FiatPaymentSuccessStatus()
        if status in ["VOIDED", "CANCELLED", "CANCELED"]:
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    def _normalize_paypal_id(self, checking_id: str) -> str:
        return (
            checking_id.replace("fiat_paypal_", "", 1)
            if checking_id.startswith("fiat_paypal_")
            else checking_id
        )

    def _serialize_metadata(
        self, payment_options: FiatSubscriptionPaymentOptions
    ) -> str:
        md = {
            "wallet_id": payment_options.wallet_id,
            "memo": payment_options.memo,
            "extra": payment_options.extra,
            "tag": payment_options.tag,
            "subscription_request_id": payment_options.subscription_request_id,
        }
        raw = json.dumps(md)
        return raw[:127]  # PayPal custom_id limit

    def _parse_create_opts(
        self, raw_opts: dict[str, Any]
    ) -> PayPalCreateInvoiceOptions | None:
        try:
            return PayPalCreateInvoiceOptions.parse_obj(raw_opts)
        except ValidationError as e:
            logger.warning(f"Invalid PayPal options: {e}")
            return None

    async def _ensure_access_token(self):
        if self._access_token and time.time() < self._token_expires_at:
            return

        r = await self.client.post(
            "/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id or "", settings.paypal_client_secret or ""),
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()
        token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 300)
        if not token:
            raise ValueError("Unable to retrieve PayPal access token.")
        self._access_token = token
        self._token_expires_at = time.time() + expires_in - 30

    def _auth_headers(self) -> dict[str, str]:
        return {**self.headers, "Authorization": f"Bearer {self._access_token}"}

    def _get_approval_url(self, links: list[dict[str, Any]]) -> str | None:
        for link in links:
            if link.get("rel") == "approve":
                return link.get("href")
        return None

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [
                str(settings.paypal_api_endpoint),
                str(settings.paypal_client_id),
                str(settings.paypal_client_secret),
                str(settings.paypal_webhook_id),
            ]
        )
