import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlencode

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

FiatMethod = Literal["checkout", "terminal", "subscription"]

STRIPE_ZERO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "JPY",
    "KMF",
    "KRW",
    "MGA",
    "PYG",
    "RWF",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}
STRIPE_THREE_DECIMAL_CURRENCIES = {"BHD", "JOD", "KWD", "OMR", "TND"}
STRIPE_WHOLE_UNIT_CURRENCIES = {"ISK", "UGX"}


class StripeTerminalOptions(BaseModel):
    class Config:
        extra = "ignore"

    capture_method: Literal["automatic", "manual"] = "automatic"
    metadata: dict[str, str] = Field(default_factory=dict)
    reader_id: str | None = None


class StripeCheckoutOptions(BaseModel):
    class Config:
        extra = "ignore"

    success_url: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    line_item_name: str | None = None


class StripeSubscriptionOptions(BaseModel):
    class Config:
        extra = "ignore"

    checking_id: str | None = None
    payment_request: str | None = None


class StripeCreateInvoiceOptions(BaseModel):
    class Config:
        extra = "ignore"

    fiat_method: FiatMethod = "checkout"
    terminal: StripeTerminalOptions | None = None
    checkout: StripeCheckoutOptions | None = None
    subscription: StripeSubscriptionOptions | None = None


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
        opts = self._parse_create_opts(extra or {})
        if not opts:
            return FiatInvoiceResponse(ok=False, error_message="Invalid Stripe options")
        try:
            amount_minor = self.amount_to_minor_units(amount, currency)
        except ValueError as exc:
            return FiatInvoiceResponse(ok=False, error_message=str(exc))

        if opts.fiat_method == "checkout":
            return await self._create_checkout_invoice(
                amount_minor, amount, currency, payment_hash, memo, opts.checkout
            )
        if opts.fiat_method == "terminal":
            return await self._create_terminal_invoice(
                amount_minor, amount, currency, payment_hash, opts.terminal
            )

        if opts.fiat_method == "subscription":
            return self._create_subscription_invoice(opts.subscription)

        return FiatInvoiceResponse(
            ok=False, error_message=f"Unsupported fiat_method: {opts.fiat_method}"
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
            or settings.stripe_payment_success_url
            or "https://lnbits.com"
        )

        if not payment_options.subscription_request_id:
            payment_options.subscription_request_id = str(uuid.uuid4())
        payment_options.extra = payment_options.extra or {}
        payment_options.extra["subscription_request_id"] = (
            payment_options.subscription_request_id
        )

        form_data: list[tuple[str, str]] = [
            ("mode", "subscription"),
            ("success_url", success_url),
            ("line_items[0][price]", subscription_id),
            ("line_items[0][quantity]", f"{quantity}"),
        ]
        subscription_data = {**payment_options.dict(), "alan_action": "subscription"}
        subscription_data["extra"] = json.dumps(subscription_data.get("extra") or {})

        form_data += self._encode_metadata(
            "subscription_data[metadata]",
            subscription_data,
        )

        try:
            r = await self.client.post(
                "/v1/checkout/sessions",
                headers=self._build_headers_form(),
                content=urlencode(form_data),
            )
            r.raise_for_status()
            data = r.json()

            url = data.get("url")
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
            params = {
                "query": f"metadata['wallet_id']:'{correlation_id}'"
                " AND "
                f"metadata['subscription_request_id']:'{subscription_id}'"
            }
            r = await self.client.get(
                "/v1/subscriptions/search",
                params=params,
            )
            r.raise_for_status()
            search_result = r.json()
            data = search_result.get("data") or []
            if not data or len(data) == 0:
                return FiatSubscriptionResponse(
                    ok=False, error_message="Subscription not found."
                )

            subscription = data[0]
            subscription_id = subscription.get("id")
            if not subscription_id:
                return FiatSubscriptionResponse(
                    ok=False, error_message="Subscription ID not found."
                )

            r = await self.client.delete(f"/v1/subscriptions/{subscription_id}")
            r.raise_for_status()

            return FiatSubscriptionResponse(ok=True)
        except Exception as exc:
            logger.warning(exc)
            return FiatSubscriptionResponse(
                ok=False, error_message="Unable to un subscribe."
            )

    async def pay_invoice(self, payment_request: str) -> FiatPaymentResponse:
        raise NotImplementedError("Stripe does not support paying invoices directly.")

    async def get_invoice_status(self, checking_id: str) -> FiatPaymentStatus:
        try:
            stripe_id = self._normalize_stripe_id(checking_id)

            if stripe_id.startswith("cs_"):
                r = await self.client.get(f"/v1/checkout/sessions/{stripe_id}")
                r.raise_for_status()
                data = r.json()
                status = self._status_from_checkout_session(data)
                amount_field = "amount_total"
                verify_amount = True

            elif stripe_id.startswith("pi_"):
                r = await self.client.get(f"/v1/payment_intents/{stripe_id}")
                r.raise_for_status()
                data = r.json()
                status = self._status_from_payment_intent(data)
                amount_field = "amount_received"
                verify_amount = True

            elif stripe_id.startswith("in_"):
                r = await self.client.get(f"/v1/invoices/{stripe_id}")
                r.raise_for_status()
                data = r.json()
                status = self._status_from_invoice(data)
                amount_field = "amount_paid"
                verify_amount = False

            else:
                logger.debug(f"Unknown Stripe id prefix: {checking_id}")
                return FiatPaymentPendingStatus()

            if (
                status.success
                and verify_amount
                and not self._amount_matches(data, amount_field)
            ):
                return FiatPaymentPendingStatus()
            return status

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

    async def _process_terminal_payment_intent(
        self, reader_id: str, payment_intent_id: str
    ) -> None:
        data = {"payment_intent": payment_intent_id}
        r = await self.client.post(
            f"/v1/terminal/readers/{reader_id}/process_payment_intent", data=data
        )
        r.raise_for_status()

    async def _create_checkout_invoice(
        self,
        amount_minor: int,
        amount: float | str,
        currency: str,
        payment_hash: str,
        memo: str | None,
        opts: StripeCheckoutOptions | None = None,
    ) -> FiatInvoiceResponse:
        co = opts or StripeCheckoutOptions()
        success_url = (
            co.success_url
            or settings.stripe_payment_success_url
            or "https://lnbits.com"
        )
        line_item_name = co.line_item_name or memo or "LNbits Invoice"

        metadata = {
            **co.metadata,
            "payment_hash": payment_hash,
            "alan_action": "invoice",
            "lnbits_amount": str(amount),
            "lnbits_currency": currency.upper(),
        }
        form_data: list[tuple[str, str]] = [
            ("mode", "payment"),
            ("success_url", success_url),
            ("line_items[0][price_data][currency]", currency.lower()),
            ("line_items[0][price_data][product_data][name]", line_item_name),
            ("line_items[0][price_data][unit_amount]", str(amount_minor)),
            ("line_items[0][quantity]", "1"),
        ]
        form_data += self._encode_metadata("metadata", metadata)

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
        amount_minor: int,
        amount: float | str,
        currency: str,
        payment_hash: str,
        opts: StripeTerminalOptions | None = None,
    ) -> FiatInvoiceResponse:
        term = opts or StripeTerminalOptions()
        metadata = {
            **term.metadata,
            "payment_hash": payment_hash,
            "source": "lnbits",
            "lnbits_amount": str(amount),
            "lnbits_currency": currency.upper(),
        }
        data: dict[str, str] = {
            "amount": str(amount_minor),
            "currency": currency.lower(),
            "payment_method_types[]": "card_present",
            "capture_method": term.capture_method,
        }
        for k, v in metadata.items():
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
            if term.reader_id:
                try:
                    await self._process_terminal_payment_intent(term.reader_id, pi_id)
                except Exception as exc:
                    logger.warning(exc)
                    return FiatInvoiceResponse(
                        ok=False,
                        error_message=(
                            "Error: unable to process PaymentIntent on reader"
                        ),
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

    def _create_subscription_invoice(
        self,
        opts: StripeSubscriptionOptions | None = None,
    ) -> FiatInvoiceResponse:
        term = opts or StripeSubscriptionOptions()

        return FiatInvoiceResponse(
            ok=True,
            checking_id=term.checking_id or urlsafe_short_hash(),
            payment_request=term.payment_request or "",
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

    def _status_from_invoice(self, invoice: dict) -> FiatPaymentStatus:
        """Map an Invoice to LNbits fiat status."""
        status = invoice.get("status")

        if status == "paid":
            return FiatPaymentSuccessStatus()

        if status in ["uncollectible", "void"]:
            return FiatPaymentFailedStatus()

        return FiatPaymentPendingStatus()

    @classmethod
    def amount_to_minor_units(cls, amount: float | str, currency: str) -> int:
        normalized_currency = currency.upper()
        exponent = cls.currency_exponent(normalized_currency)
        decimal_amount = Decimal(str(amount))
        if not decimal_amount.is_finite() or decimal_amount <= 0:
            raise ValueError("Stripe amount must be a positive finite number.")
        if (
            normalized_currency in STRIPE_WHOLE_UNIT_CURRENCIES
            and decimal_amount != decimal_amount.to_integral_value()
        ):
            raise ValueError(
                f"Stripe does not support fractional {normalized_currency} amounts."
            )

        amount_minor = decimal_amount * (Decimal(10) ** exponent)
        if amount_minor != amount_minor.to_integral_value():
            raise ValueError(
                f"Stripe {normalized_currency} amounts support at most "
                f"{exponent} decimal places."
            )
        return int(amount_minor)

    @classmethod
    def minor_units_to_amount(cls, amount: int, currency: str) -> float:
        scale = Decimal(10) ** cls.currency_exponent(currency)
        return float(Decimal(amount) / scale)

    @classmethod
    def currency_exponent(cls, currency: str) -> int:
        normalized_currency = currency.upper()
        if normalized_currency in STRIPE_ZERO_DECIMAL_CURRENCIES:
            return 0
        if normalized_currency in STRIPE_THREE_DECIMAL_CURRENCIES:
            return 3
        return 2

    @classmethod
    def _amount_matches(
        cls,
        data: dict,
        amount_field: str,
    ) -> bool:
        metadata = data.get("metadata") or {}
        expected_amount = metadata.get("lnbits_amount")
        expected_currency = metadata.get("lnbits_currency")
        if expected_amount is None or not expected_currency:
            logger.warning("Stripe payment is missing LNbits amount metadata.")
            return False

        actual_amount = data.get(amount_field)
        actual_currency = data.get("currency")
        if actual_amount is None or not actual_currency:
            logger.warning("Stripe payment response is missing amount or currency.")
            return False

        expected_amount_minor = cls.amount_to_minor_units(
            expected_amount, expected_currency
        )
        matches = (
            int(actual_amount) == expected_amount_minor
            and str(actual_currency).upper() == expected_currency.upper()
        )
        if not matches:
            logger.warning("Stripe payment amount or currency does not match invoice.")
        return matches

    def _build_headers_form(self) -> dict[str, str]:
        return {**self.headers, "Content-Type": "application/x-www-form-urlencoded"}

    def _encode_metadata(
        self, prefix: str, md: dict[str, Any]
    ) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for k, v in (md or {}).items():
            out.append((f"{prefix}[{k}]", str(v or "")))
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
