import asyncio
import ipaddress
import json
from collections.abc import AsyncGenerator
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from urllib.parse import urlparse

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


REVOLUT_WEBHOOK_EVENTS = [
    "ORDER_AUTHORISED",
    "ORDER_COMPLETED",
    "SUBSCRIPTION_INITIATED",
]

ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
THREE_DECIMAL_CURRENCIES = {
    "BHD",
    "IQD",
    "JOD",
    "KWD",
    "LYD",
    "OMR",
    "TND",
}
REVOLUT_CUSTOMER_LIST_LIMIT = 500
REVOLUT_CUSTOMER_LIST_MAX_PAGES = 20
REVOLUT_REQUEST_TIMEOUT = 30


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
            r = await self.client.get(
                "/api/orders",
                params={"limit": 1},
                timeout=REVOLUT_REQUEST_TIMEOUT,
            )
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
            return FiatInvoiceResponse(
                ok=False, error_message="Invalid Revolut options"
            )

        amount_minor = self.amount_to_minor_units(amount, currency)
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
            r = await self.client.post(
                "/api/orders", json=payload, timeout=REVOLUT_REQUEST_TIMEOUT
            )
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
            "external_reference": self._serialize_subscription_reference(reference),
            "setup_order_redirect_url": (
                payment_options.success_url
                or settings.revolut_payment_success_url
                or "https://lnbits.com"
            ),
        }
        if extra.get("trial_duration"):
            payload["trial_duration"] = extra["trial_duration"]

        headers = {
            **self.headers,
            "Idempotency-Key": payment_options.subscription_request_id,
        }

        try:
            customer_id, customer_error = await self._get_subscription_customer_id(
                payment_options
            )
            if not customer_id:
                return FiatSubscriptionResponse(ok=False, error_message=customer_error)
            payload["customer_id"] = customer_id
            r = await self.client.post(
                "/api/subscriptions",
                json=payload,
                headers=headers,
                timeout=REVOLUT_REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            revolut_subscription_id = data.get("id")
            setup_order_id = data.get("setup_order_id")
            if not revolut_subscription_id or not setup_order_id:
                return FiatSubscriptionResponse(
                    ok=False,
                    error_message=(
                        "Server error: missing subscription id or setup order id"
                    ),
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
            r = await self.client.post(
                f"/api/subscriptions/{subscription_id}/cancel",
                timeout=REVOLUT_REQUEST_TIMEOUT,
            )
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
        r = await self.client.get(
            f"/api/orders/{order_id}", timeout=REVOLUT_REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return r.json()

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        r = await self.client.get(
            f"/api/subscriptions/{subscription_id}", timeout=REVOLUT_REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return r.json()

    async def get_subscription_cycle(
        self, subscription_id: str, cycle_id: str
    ) -> dict[str, Any]:
        r = await self.client.get(
            f"/api/subscriptions/{subscription_id}/cycles/{cycle_id}",
            timeout=REVOLUT_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    async def _get_subscription_customer_id(
        self, payment_options: FiatSubscriptionPaymentOptions
    ) -> tuple[str | None, str | None]:
        if not payment_options.customer_email:
            return (
                None,
                "Revolut subscriptions require customer_email.",
            )

        customer = await self._get_customer_by_email(payment_options.customer_email)
        customer_id = customer.get("id") if customer else None
        if customer_id:
            return customer_id, None

        customer = await self._create_customer(payment_options.customer_email)
        customer_id = customer.get("id")
        if not customer_id:
            return None, "Server error: missing customer id"
        return customer_id, None

    async def _get_customer_by_email(self, email: str) -> dict[str, Any] | None:
        page_token = None
        for _ in range(REVOLUT_CUSTOMER_LIST_MAX_PAGES):
            customer_page = await self._list_customers(page_token=page_token)
            customer = _find_customer_by_email(customer_page["customers"], email)
            if customer:
                return customer

            page_token = customer_page.get("next_page_token")
            if not page_token:
                return None
        return None

    async def _list_customers(self, page_token: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": REVOLUT_CUSTOMER_LIST_LIMIT}
        if page_token:
            params["page_token"] = page_token
        r = await self.client.get(
            "/api/customers", params=params, timeout=REVOLUT_REQUEST_TIMEOUT
        )
        r.raise_for_status()
        return _extract_customer_page(r.json())

    async def _create_customer(self, email: str) -> dict[str, Any]:
        r = await self.client.post(
            "/api/customers",
            json={"email": email},
            timeout=REVOLUT_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()

    @classmethod
    async def create_webhook(
        cls,
        url: str,
        endpoint: str | None = None,
        api_secret_key: str | None = None,
        api_version: str | None = None,
    ) -> dict[str, Any]:
        if not url:
            raise ValueError("Missing Revolut webhook URL.")
        cls._validate_webhook_url(url)
        if not endpoint and not settings.revolut_api_endpoint:
            raise ValueError("Missing Revolut API endpoint.")
        if not api_secret_key and not settings.revolut_api_secret_key:
            raise ValueError("Missing Revolut API secret key.")

        base_url = normalize_endpoint(endpoint or settings.revolut_api_endpoint)
        secret_key = api_secret_key or settings.revolut_api_secret_key
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Revolut-Api-Version": api_version or settings.revolut_api_version,
            "Content-Type": "application/json",
            "User-Agent": settings.user_agent,
        }
        payload = {"url": url, "events": REVOLUT_WEBHOOK_EVENTS}
        async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
            webhooks = await cls._list_webhooks(client)
            existing = await cls._get_existing_webhook(client, webhooks, url)
            if existing:
                existing["already_exists"] = True
                return existing

            response = await client.post(
                "/api/webhooks", json=payload, timeout=REVOLUT_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()

    @classmethod
    async def _list_webhooks(cls, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get("/api/webhooks", timeout=REVOLUT_REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for field in ["webhooks", "data", "items"]:
                if isinstance(data.get(field), list):
                    return data[field]
        return []

    @classmethod
    async def _get_existing_webhook(
        cls, client: httpx.AsyncClient, webhooks: list[dict[str, Any]], url: str
    ) -> dict[str, Any] | None:
        for webhook in webhooks:
            if cls._normalize_webhook_url(webhook.get("url")) != (
                cls._normalize_webhook_url(url)
            ):
                continue

            webhook_id = webhook.get("id")
            if webhook_id and (
                not webhook.get("events") or not webhook.get("signing_secret")
            ):
                response = await client.get(
                    f"/api/webhooks/{webhook_id}", timeout=REVOLUT_REQUEST_TIMEOUT
                )
                response.raise_for_status()
                webhook = response.json()

            events = set(webhook.get("events") or [])
            missing_events = set(REVOLUT_WEBHOOK_EVENTS) - events
            if missing_events:
                raise ValueError(
                    "A Revolut webhook already exists for this URL, but it is "
                    f"missing required events: {', '.join(sorted(missing_events))}."
                )

            if not webhook.get("signing_secret"):
                raise ValueError(
                    "A Revolut webhook already exists for this URL, but Revolut "
                    "did not return a signing secret."
                )

            return webhook
        return None

    @classmethod
    def _normalize_webhook_url(cls, url: str | None) -> str:
        return (url or "").strip().rstrip("/")

    @classmethod
    def _validate_webhook_url(cls, url: str) -> None:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if parsed.scheme not in ["http", "https"] or not hostname:
            raise ValueError("Revolut webhook URL must be a clearnet URL.")

        host = hostname.lower()
        if host == "localhost" or host.endswith(".localhost"):
            raise ValueError("Revolut webhook URL must be a clearnet URL.")
        if host.endswith(".local") or host.endswith(".onion"):
            raise ValueError("Revolut webhook URL must be a clearnet URL.")

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return

        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError("Revolut webhook URL must be a clearnet URL.")

    def _status_from_order(self, order: dict[str, Any]) -> FiatPaymentStatus:
        status = (order.get("state") or "").upper()
        if status == "COMPLETED":
            return FiatPaymentSuccessStatus()
        if status in ["CANCELLED", "FAILED"]:
            return FiatPaymentFailedStatus()
        return FiatPaymentPendingStatus()

    @classmethod
    def amount_to_minor_units(cls, amount: float | Decimal, currency: str) -> int:
        scale = Decimal(10) ** cls.currency_exponent(currency)
        return int((Decimal(str(amount)) * scale).quantize(Decimal("1"), ROUND_HALF_UP))

    @classmethod
    def minor_units_to_amount(cls, amount: int, currency: str) -> float:
        scale = Decimal(10) ** cls.currency_exponent(currency)
        return float(Decimal(amount) / scale)

    @classmethod
    def currency_exponent(cls, currency: str) -> int:
        normalized = currency.upper()
        if normalized in ZERO_DECIMAL_CURRENCIES:
            return 0
        if normalized in THREE_DECIMAL_CURRENCIES:
            return 3
        return 2

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
            return RevolutSubscriptionReference.parse_obj(
                json.loads(external_reference)
            )
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


def _extract_customer_page(data: Any) -> dict[str, Any]:
    if isinstance(data, list):
        return {"customers": _filter_customer_list(data)}
    if isinstance(data, dict):
        for field in ["customers", "data", "items"]:
            customers = data.get(field)
            if isinstance(customers, list):
                return {
                    "customers": _filter_customer_list(customers),
                    "next_page_token": data.get("next_page_token"),
                }
    return {"customers": []}


def _filter_customer_list(customers: list[Any]) -> list[dict[str, Any]]:
    return [customer for customer in customers if isinstance(customer, dict)]


def _find_customer_by_email(
    customers: list[dict[str, Any]], email: str
) -> dict[str, Any] | None:
    normalized_email = email.casefold()
    for customer in customers:
        if str(customer.get("email") or "").casefold() == normalized_email:
            return customer
    return None
