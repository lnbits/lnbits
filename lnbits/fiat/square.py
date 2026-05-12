import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any, Literal

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

FiatMethod = Literal["checkout", "subscription"]


class SquareCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    line_item_name: str | None = None


class SquareSubscriptionOptions(BaseModel):
    class Config:
        extra = "ignore"

    checking_id: str | None = None
    payment_request: str | None = None


class SquareCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    fiat_method: FiatMethod = "checkout"
    checkout: SquareCheckoutOptions | None = None
    subscription: SquareSubscriptionOptions | None = None


class SquareSubscriptionCheckoutInfo(BaseModel):
    plan_variation_id: str
    price_money: dict[str, Any]


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

        if opts.fiat_method == "subscription":
            return self._create_subscription_invoice(opts.subscription)

        return await self._create_checkout_invoice(
            amount=amount,
            payment_hash=payment_hash,
            currency=currency,
            opts=opts,
            memo=memo,
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
            or settings.square_payment_success_url
            or "https://lnbits.com"
        )

        if not payment_options.subscription_request_id:
            payment_options.subscription_request_id = urlsafe_short_hash()
        payment_options.extra = payment_options.extra or {}
        payment_options.extra["subscription_request_id"] = (
            payment_options.subscription_request_id
        )
        try:
            checkout_info = await self._get_subscription_checkout_info(subscription_id)
            metadata = self._serialize_metadata(payment_options)
            payload = {
                "idempotency_key": payment_options.subscription_request_id,
                "description": metadata,
                "quick_pay": {
                    "name": (payment_options.memo or "LNbits Subscription")[:255],
                    "price_money": checkout_info.price_money,
                    "location_id": self.location_id,
                },
                "checkout_options": {
                    "redirect_url": success_url,
                    "subscription_plan_id": checkout_info.plan_variation_id,
                },
                "payment_note": metadata,
            }
            r = await self.client.post(
                "/v2/online-checkout/payment-links", json=payload
            )
            r.raise_for_status()
            data = r.json()
            payment_link = data.get("payment_link") or {}
            url = payment_link.get("url")
            if not url:
                return FiatSubscriptionResponse(
                    ok=False, error_message="Server error: missing url"
                )
            return FiatSubscriptionResponse(
                ok=True,
                checkout_session_url=url,
                subscription_request_id=payment_options.subscription_request_id,
            )
        except json.JSONDecodeError as exc:
            logger.warning(exc)
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
            square_subscription_id = await self._get_square_subscription_id(
                subscription_id, correlation_id
            )
            r = await self.client.post(
                f"/v2/subscriptions/{square_subscription_id}/cancel"
            )
            r.raise_for_status()
            return FiatSubscriptionResponse(ok=True)
        except Exception as exc:
            logger.warning(exc)
            return FiatSubscriptionResponse(
                ok=False, error_message="Unable to cancel subscription."
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
        order = await self._get_order(order_id)
        payment_id = self._payment_id_from_order(order)
        if payment_id:
            return await self._get_payment_status(payment_id)

        if (order.get("state") or "").upper() == "CANCELED":
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    async def _get_order(self, order_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/v2/orders/{order_id}")
        r.raise_for_status()
        return r.json().get("order") or {}

    async def get_payment_for_order(self, order_id: str) -> dict[str, Any] | None:
        order = await self._get_order(order_id)
        payment_id = self._payment_id_from_order(order)
        if not payment_id:
            return None
        return await self._get_payment(payment_id)

    def _payment_id_from_order(self, order: dict[str, Any]) -> str | None:
        tenders = order.get("tenders") or []
        for tender in tenders:
            payment_id = tender.get("payment_id")
            if payment_id:
                return payment_id
        return None

    async def _get_payment_status(self, payment_id: str) -> FiatPaymentStatus:
        return self._status_from_payment(await self._get_payment(payment_id))

    async def _get_payment(self, payment_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/v2/payments/{payment_id}")
        r.raise_for_status()
        return r.json().get("payment") or {}

    async def _get_subscription_checkout_info(
        self, subscription_plan_id: str
    ) -> SquareSubscriptionCheckoutInfo:
        catalog_object = await self._get_catalog_object(subscription_plan_id)
        if catalog_object.get("type") == "SUBSCRIPTION_PLAN":
            return await self._get_plan_checkout_info(catalog_object)

        if catalog_object.get("type") == "SUBSCRIPTION_PLAN_VARIATION":
            price_money = await self._get_subscription_price_money(
                catalog_object,
            )
            plan_variation_id = catalog_object.get("id")
            if not plan_variation_id:
                raise ValueError("Square subscription plan variation is missing an ID.")
            return SquareSubscriptionCheckoutInfo(
                plan_variation_id=plan_variation_id,
                price_money=price_money,
            )

        raise ValueError(
            "Square subscription ID must be a plan ID or plan variation ID."
        )

    async def _get_plan_checkout_info(
        self, catalog_object: dict[str, Any]
    ) -> SquareSubscriptionCheckoutInfo:
        plan_data = catalog_object.get("subscription_plan_data") or {}
        plan_variations = plan_data.get("subscription_plan_variations") or []
        plan_variation = next(
            (
                variation
                for variation in plan_variations
                if not variation.get("is_deleted")
            ),
            None,
        )
        if not plan_variation:
            raise ValueError("Square subscription plan is missing a variation.")

        price_money = await self._get_subscription_price_money(
            plan_variation,
            eligible_item_ids=plan_data.get("eligible_item_ids") or [],
        )
        plan_variation_id = plan_variation.get("id")
        if not plan_variation_id:
            raise ValueError("Square subscription plan variation is missing an ID.")

        return SquareSubscriptionCheckoutInfo(
            plan_variation_id=plan_variation_id,
            price_money=price_money,
        )

    async def _get_catalog_object(self, object_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/v2/catalog/object/{object_id}")
        r.raise_for_status()
        return r.json().get("object") or {}

    async def _get_subscription_price_money(
        self,
        plan_variation: dict[str, Any],
        eligible_item_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        variation_data = plan_variation.get("subscription_plan_variation_data") or {}
        phases = variation_data.get("phases") or []
        for phase in phases:
            pricing = phase.get("pricing") or {}
            price_money = pricing.get("price_money") or phase.get(
                "recurring_price_money"
            )
            parsed_price_money = self._parse_price_money(price_money)
            if parsed_price_money:
                return parsed_price_money

            if pricing.get("type") == "RELATIVE":
                return await self._get_relative_subscription_price_money(
                    eligible_item_ids or []
                )

        raise ValueError("Square subscription plan variation is missing price_money.")

    async def _get_relative_subscription_price_money(
        self, eligible_item_ids: list[str]
    ) -> dict[str, Any]:
        if len(eligible_item_ids) != 1:
            raise ValueError(
                "Square relative subscription plan must have exactly one item."
            )

        item = await self._get_catalog_object(eligible_item_ids[0])
        item_variations: list[dict[str, Any]] = []
        if item.get("type") == "ITEM":
            item_variations = (item.get("item_data") or {}).get("variations") or []
        elif item.get("type") == "ITEM_VARIATION":
            item_variations = [item]

        item_variation = next(
            (
                variation
                for variation in item_variations
                if not variation.get("is_deleted")
            ),
            None,
        )
        if not item_variation:
            raise ValueError("Square subscription item is missing a variation.")

        price_money = self._parse_price_money(
            (item_variation.get("item_variation_data") or {}).get("price_money")
        )
        if price_money:
            return price_money

        raise ValueError("Square subscription item variation is missing price_money.")

    def _parse_price_money(
        self, price_money: dict[str, Any] | None
    ) -> dict[str, Any] | None:
        if (
            price_money
            and price_money.get("amount") is not None
            and price_money.get("currency")
        ):
            return {
                "amount": int(price_money["amount"]),
                "currency": price_money["currency"].upper(),
            }
        return None

    def _status_from_payment(self, payment: dict[str, Any]) -> FiatPaymentStatus:
        status = (payment.get("status") or "").upper()
        if status == "COMPLETED":
            return FiatPaymentSuccessStatus()
        if status in ["CANCELED", "FAILED"]:
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    async def _create_checkout_invoice(
        self,
        amount: float,
        payment_hash: str,
        currency: str,
        opts: SquareCreateInvoiceOptions,
        memo: str | None = None,
    ) -> FiatInvoiceResponse:
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

    def _create_subscription_invoice(
        self, opts: SquareSubscriptionOptions | None
    ) -> FiatInvoiceResponse:
        term = opts or SquareSubscriptionOptions()
        checking_id = term.checking_id or f"payment_{urlsafe_short_hash()}"
        return FiatInvoiceResponse(
            ok=True,
            checking_id=checking_id,
            payment_request=term.payment_request or "",
        )

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

    def _serialize_metadata(
        self, payment_options: FiatSubscriptionPaymentOptions
    ) -> str:
        extra_link = None
        if payment_options.extra:
            raw_link = payment_options.extra.get("link")
            extra_link = str(raw_link)[:200] if raw_link else None

        meta = [
            payment_options.wallet_id,
            payment_options.tag,
            payment_options.subscription_request_id,
            extra_link,
        ]

        memo_limit = 493 - len(json.dumps(meta, separators=(",", ":")))
        if memo_limit > 0 and payment_options.memo:
            meta.append(payment_options.memo[:memo_limit])
        else:
            meta.append(None)

        metadata = json.dumps(meta, separators=(",", ":"))
        if len(metadata) > 500:
            raise ValueError("Square subscription metadata is too long.")
        return metadata

    async def _get_square_subscription_id(
        self, subscription_id: str, wallet_id: str
    ) -> str:
        from lnbits.core.crud.payments import get_latest_payment_by_extra_key_value

        payment = await get_latest_payment_by_extra_key_value(
            "subscription_request_id", subscription_id, wallet_id=wallet_id
        )
        if not payment:
            return subscription_id
        square_subscription_id = (payment.extra or {}).get("square_subscription_id")
        return square_subscription_id or subscription_id

    def _settings_connection_fields(self) -> str:
        return "-".join(
            [
                str(settings.square_api_endpoint),
                str(settings.square_access_token),
                str(settings.square_location_id),
                str(settings.square_api_version),
            ]
        )
