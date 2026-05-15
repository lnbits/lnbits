import asyncio
import json
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


class RevolutCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    description: str | None = None


class RevolutCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    checkout: RevolutCheckoutOptions | None = None


class RevolutSubscriptionReference(BaseModel):
    wallet_id: str
    tag: str | None = None
    subscription_request_id: str | None = None
    extra: dict[str, Any] | None = None
    memo: str | None = None


class RevolutWallet(FiatProvider):
    """https://developer.revolut.com/docs/merchant"""

    def __init__(self):
        logger.debug("Initializing RevolutWallet")
        self._settings_fields = self._settings_connection_fields()
        if not settings.revolut_api_endpoint:
            raise ValueError("Cannot initialize RevolutWallet: missing endpoint.")
        if not settings.revolut_api_secret_key:
            raise ValueError("Cannot initialize RevolutWallet: missing API secret key.")

        self.endpoint = normalize_endpoint(settings.revolut_api_endpoint)
        self.headers = {
            "Authorization": f"Bearer {settings.revolut_api_secret_key}",
            "Revolut-Api-Version": settings.revolut_api_version,
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent,
        }
        self.client = httpx.AsyncClient(base_url=self.endpoint, headers=self.headers)
        logger.info("RevolutWallet initialized.")

    async def cleanup(self):
        try:
            await self.client.aclose()
        except RuntimeError as e:
            logger.warning(f"Error closing Revolut wallet connection: {e}")

    async def status(
        self, only_check_settings: bool | None = False
    ) -> FiatStatusResponse:
        if only_check_settings:
            if self._settings_fields != self._settings_connection_fields():
                return FiatStatusResponse("Connection settings have changed.", 0)
            return FiatStatusResponse(balance=0)

        try:
            r = await self.client.get("/api/orders", params={"limit": 1}, timeout=15)
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
        if opts is None:
            return FiatInvoiceResponse(ok=False, error_message="Invalid Revolut options")

        amount_minor = int(amount * 100)
        checkout = opts.checkout or RevolutCheckoutOptions()
        success_url = (
            checkout.success_url
            or settings.revolut_payment_success_url
            or "https://lnbits.com"
        )

        payload = {
            "amount": amount_minor,
            "currency": currency.upper(),
            "description": checkout.description or memo or "LNbits Invoice",
            "redirect_url": success_url,
            "metadata": {
                **checkout.metadata,
                "payment_hash": payment_hash,
                "alan_action": "invoice",
            },
        }

        try:
            r = await self.client.post("/api/orders", json=payload)
            r.raise_for_status()
            data = r.json()
            order_id = data.get("id")
            checkout_url = data.get("checkout_url")
            if not order_id or not checkout_url:
                return FiatInvoiceResponse(
                    ok=False, error_message="Server error: missing order id or url"
                )
            return FiatInvoiceResponse(
                ok=True,
                checking_id=f"order_{order_id}",
                payment_request=checkout_url,
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
        if quantity != 1:
            return FiatSubscriptionResponse(
                ok=False,
                error_message="Revolut subscriptions do not support quantity.",
            )

        wallet_id = payment_options.wallet_id
        if not wallet_id:
            return FiatSubscriptionResponse(
                ok=False, error_message="Wallet ID is required."
            )

        extra = payment_options.extra or {}
        customer_id = extra.get("customer_id")
        if not customer_id:
            return FiatSubscriptionResponse(
                ok=False,
                error_message="Revolut subscriptions require extra.customer_id.",
            )

        if not payment_options.subscription_request_id:
            payment_options.subscription_request_id = urlsafe_short_hash()

        reference = RevolutSubscriptionReference(
            wallet_id=wallet_id,
            tag=payment_options.tag,
            subscription_request_id=payment_options.subscription_request_id,
            extra=extra,
            memo=payment_options.memo,
        )
        payload: dict[str, Any] = {
            "plan_variation_id": subscription_id,
            "customer_id": customer_id,
            "external_reference": self._serialize_subscription_reference(reference),
            "setup_order_redirect_url": (
                payment_options.success_url
                or settings.revolut_payment_success_url
                or "https://lnbits.com"
            ),
        }
        if extra.get("trial_duration"):
            payload["trial_duration"] = extra["trial_duration"]

        headers = {**self.headers, "Idempotency-Key": payment_options.subscription_request_id}

        try:
            r = await self.client.post("/api/subscriptions", json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
            revolut_subscription_id = data.get("id")
            setup_order_id = data.get("setup_order_id")
            if not revolut_subscription_id or not setup_order_id:
                return FiatSubscriptionResponse(
                    ok=False,
                    error_message="Server error: missing subscription id or setup order id",
                )

            setup_order = await self.get_order(setup_order_id)
            checkout_url = setup_order.get("checkout_url")
            if not checkout_url:
                return FiatSubscriptionResponse(
                    ok=False, error_message="Server error: missing setup checkout url"
                )

            return FiatSubscriptionResponse(
                ok=True,
                checkout_session_url=checkout_url,
                subscription_request_id=revolut_subscription_id,
            )
        except json.JSONDecodeError:
            return FiatSubscriptionResponse(
                ok=False, error_message="Server error: invalid json response"
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
            r = await self.client.post(f"/api/subscriptions/{subscription_id}/cancel")
            r.raise_for_status()
            return FiatSubscriptionResponse(ok=True)
        except Exception as exc:
            logger.warning(exc)
            return FiatSubscriptionResponse(
                ok=False, error_message="Unable to cancel subscription."
            )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Revolut does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            order_id = self._normalize_revolut_id(checking_id)
            return self._status_from_order(await self.get_order(order_id))
        except Exception as exc:
            logger.debug(f"Error getting Revolut invoice status: {exc}")
            return FiatPaymentPendingStatus()

    async def get_payment_status(self, checking_id: str) -> FiatPaymentStatus:
        raise NotImplementedError("Revolut does not support outgoing payments.")

    async def paid_invoices_stream(self) -> AsyncGenerator[str, None]:
        logger.warning(
            "Revolut does not support paid invoices stream. Use webhooks instead."
        )
        mock_queue: asyncio.Queue[str] = asyncio.Queue(0)
        while settings.lnbits_running:
            value = await mock_queue.get()
            yield value

    def _normalize_revolut_id(self, checking_id: str) -> str:
        value = (
            checking_id.replace("fiat_revolut_", "", 1)
            if checking_id.startswith("fiat_revolut_")
            else checking_id
        )
        return value.replace("order_", "", 1) if value.startswith("order_") else value

    async def get_order(self, order_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/api/orders/{order_id}")
        r.raise_for_status()
        return r.json()

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/api/subscriptions/{subscription_id}")
        r.raise_for_status()
        return r.json()

    async def get_subscription_cycle(
        self, subscription_id: str, cycle_id: str
    ) -> dict[str, Any]:
        r = await self.client.get(f"/api/subscriptions/{subscription_id}/cycles/{cycle_id}")
        r.raise_for_status()
        return r.json()

    def _status_from_order(self, order: dict[str, Any]) -> FiatPaymentStatus:
        status = (order.get("state") or "").upper()
        if status == "COMPLETED":
            return FiatPaymentSuccessStatus()
        if status in ["CANCELLED", "FAILED"]:
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    def _parse_create_opts(
        self, raw_opts: dict[str, Any]
    ) -> RevolutCreateInvoiceOptions | None:
        try:
            return RevolutCreateInvoiceOptions.parse_obj(raw_opts)
        except ValidationError as e:
            logger.warning(f"Invalid Revolut options: {e}")
            return None

    def _serialize_subscription_reference(
        self, reference: RevolutSubscriptionReference
    ) -> str:
        payload = reference.dict(exclude_none=True)
        serialized = json.dumps(payload, separators=(",", ":"))
        if len(serialized) > 1024:
            raise ValueError("Revolut subscription external_reference is too long.")
        return serialized

    def deserialize_subscription_reference(
        self, external_reference: str | None
    ) -> RevolutSubscriptionReference | None:
        if not external_reference:
            return None
        try:
            return RevolutSubscriptionReference.parse_obj(json.loads(external_reference))
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(exc)
            return None

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [
                str(settings.revolut_api_endpoint),
                str(settings.revolut_api_secret_key),
                str(settings.revolut_api_version),
                str(settings.revolut_webhook_signing_secret),
            ]
        )
