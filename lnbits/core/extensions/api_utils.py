from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .api import extension_api_method
from .models import (
    Bolt11Request,
    CurrencyConvertRequest,
    CurrencyConvertResponse,
    CurrencyListResponse,
    CurrencyRateRequest,
    CurrencyRateResponse,
    DecodeInvoiceResponse,
    EmptyRequest,
    FiatToSatsRequest,
    FiatToSatsResponse,
    InvoiceAmountMsatResponse,
    InvoiceExpiryResponse,
    InvoiceMemoResponse,
    InvoicePaymentHashResponse,
    RandomSecretAndHashRequest,
    RandomSecretAndHashResponse,
    SatsToFiatRequest,
    SatsToFiatResponse,
    ServerHealthResponse,
    ValidateInvoiceResponse,
    VerifyPreimageRequest,
    VerifyPreimageResponse,
)

if TYPE_CHECKING:
    from .api import ExtensionAPI


class ExtensionAPIUtils:
    def __init__(self, api: ExtensionAPI) -> None:
        self.api = api
        self.currencies = ExtensionCurrencyUtils(api)
        self.server = ExtensionServerUtils(api)
        self.lightning = ExtensionLightningUtils(api)


class _ExtensionAPIUtilsGroup:
    def __init__(self, api: ExtensionAPI) -> None:
        self.api = api


class ExtensionCurrencyUtils(_ExtensionAPIUtilsGroup):
    @extension_api_method(
        method_id="utils.currencies.list",
        namespace="utils.currencies",
        name="List currencies",
        host_interface="utils-currencies",
        host_name="list_currencies",
        sdk_name="list",
        description="List currencies supported by LNbits exchange-rate conversion.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def list(self, request: EmptyRequest) -> CurrencyListResponse:
        from lnbits.utils.exchange_rates import allowed_currencies

        return CurrencyListResponse(currencies=allowed_currencies())

    @extension_api_method(
        method_id="utils.currencies.rate",
        namespace="utils.currencies",
        name="Get currency rate",
        host_interface="utils-currencies",
        host_name="rate",
        sdk_name="rate",
        description="Get sats-per-fiat and BTC price for a currency.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def rate(self, request: CurrencyRateRequest) -> CurrencyRateResponse:
        from lnbits.utils.exchange_rates import get_fiat_rate_and_price_satoshis

        rate, price = await get_fiat_rate_and_price_satoshis(request.currency)
        return CurrencyRateResponse(rate=rate, price=price)

    @extension_api_method(
        method_id="utils.currencies.convert",
        namespace="utils.currencies",
        name="Convert currency amount",
        host_interface="utils-currencies",
        host_name="convert",
        sdk_name="convert",
        description="Convert between sats, BTC, and supported fiat currencies.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def convert(self, request: CurrencyConvertRequest) -> CurrencyConvertResponse:
        from lnbits.utils.exchange_rates import (
            fiat_amount_as_satoshis,
            satoshis_amount_as_fiat,
        )

        from_currency = request.from_currency
        if from_currency == "sats":
            from_currency = "sat"

        amounts: list[tuple[str, float]] = []
        if from_currency == "sat":
            sats = int(request.amount)
            amounts.append(("BTC", sats / 100_000_000))
            amounts.append(("sats", sats))
            for currency in request.to.split(","):
                currency = currency.strip()
                if currency:
                    amounts.append(
                        (
                            currency.upper(),
                            await satoshis_amount_as_fiat(sats, currency),
                        )
                    )
        else:
            sats = await fiat_amount_as_satoshis(request.amount, from_currency)
            amounts.append((from_currency.upper(), request.amount))
            amounts.append(("sats", sats))
            amounts.append(("BTC", sats / 100_000_000))
        return CurrencyConvertResponse(amounts=amounts)

    @extension_api_method(
        method_id="utils.currencies.fiat_to_sats",
        namespace="utils.currencies",
        name="Convert fiat to sats",
        host_interface="utils-currencies",
        host_name="fiat_to_sats",
        sdk_name="fiatToSats",
        description="Convert a fiat amount to sats.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def fiat_to_sats(self, request: FiatToSatsRequest) -> FiatToSatsResponse:
        from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

        return FiatToSatsResponse(
            amount_sat=await fiat_amount_as_satoshis(
                request.amount,
                request.currency,
            )
        )

    @extension_api_method(
        method_id="utils.currencies.sats_to_fiat",
        namespace="utils.currencies",
        name="Convert sats to fiat",
        host_interface="utils-currencies",
        host_name="sats_to_fiat",
        sdk_name="satsToFiat",
        description="Convert a sats amount to fiat.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def sats_to_fiat(self, request: SatsToFiatRequest) -> SatsToFiatResponse:
        from lnbits.utils.exchange_rates import satoshis_amount_as_fiat

        return SatsToFiatResponse(
            amount=await satoshis_amount_as_fiat(request.amount, request.currency)
        )


class ExtensionServerUtils(_ExtensionAPIUtilsGroup):
    @extension_api_method(
        method_id="utils.server.health",
        namespace="utils.server",
        name="Server health",
        host_interface="utils-server",
        host_name="health",
        sdk_name="health",
        description="Return basic public LNbits server health data.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def health(self, request: EmptyRequest) -> ServerHealthResponse:
        from lnbits.settings import settings

        return ServerHealthResponse(
            server_time=int(time.time()),
            up_time=settings.lnbits_server_up_time,
        )


class ExtensionLightningUtils(_ExtensionAPIUtilsGroup):
    @extension_api_method(
        method_id="utils.lightning.decode_invoice",
        namespace="utils.lightning",
        name="Decode Lightning invoice",
        host_interface="utils-lightning",
        host_name="decode_invoice",
        sdk_name="decodeInvoice",
        description="Decode a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def decode_invoice(self, request: Bolt11Request) -> DecodeInvoiceResponse:
        invoice = _decode_bolt11(request.bolt11)
        return _decoded_invoice_response(invoice)

    @extension_api_method(
        method_id="utils.lightning.validate_invoice",
        namespace="utils.lightning",
        name="Validate Lightning invoice",
        host_interface="utils-lightning",
        host_name="validate_invoice",
        sdk_name="validateInvoice",
        description="Validate whether a string is a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def validate_invoice(self, request: Bolt11Request) -> ValidateInvoiceResponse:
        try:
            _decode_bolt11(request.bolt11)
            return ValidateInvoiceResponse(valid=True)
        except Exception as exc:
            return ValidateInvoiceResponse(valid=False, error=str(exc))

    @extension_api_method(
        method_id="utils.lightning.invoice_payment_hash",
        namespace="utils.lightning",
        name="Get Lightning invoice payment hash",
        host_interface="utils-lightning",
        host_name="invoice_payment_hash",
        sdk_name="invoicePaymentHash",
        description="Get the payment hash from a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def invoice_payment_hash(
        self, request: Bolt11Request
    ) -> InvoicePaymentHashResponse:
        return InvoicePaymentHashResponse(
            payment_hash=str(_decode_bolt11(request.bolt11).payment_hash)
        )

    @extension_api_method(
        method_id="utils.lightning.invoice_amount_msat",
        namespace="utils.lightning",
        name="Get Lightning invoice amount",
        host_interface="utils-lightning",
        host_name="invoice_amount_msat",
        sdk_name="invoiceAmountMsat",
        description="Get the amount in msat from a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def invoice_amount_msat(
        self, request: Bolt11Request
    ) -> InvoiceAmountMsatResponse:
        return InvoiceAmountMsatResponse(
            amount_msat=_invoice_amount_msat(_decode_bolt11(request.bolt11))
        )

    @extension_api_method(
        method_id="utils.lightning.invoice_expiry",
        namespace="utils.lightning",
        name="Get Lightning invoice expiry",
        host_interface="utils-lightning",
        host_name="invoice_expiry",
        sdk_name="invoiceExpiry",
        description="Get the expiry timestamp from a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def invoice_expiry(self, request: Bolt11Request) -> InvoiceExpiryResponse:
        return InvoiceExpiryResponse(
            expires_at=_invoice_expires_at(_decode_bolt11(request.bolt11))
        )

    @extension_api_method(
        method_id="utils.lightning.invoice_memo",
        namespace="utils.lightning",
        name="Get Lightning invoice memo",
        host_interface="utils-lightning",
        host_name="invoice_memo",
        sdk_name="invoiceMemo",
        description="Get the memo from a BOLT11 Lightning invoice.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def invoice_memo(self, request: Bolt11Request) -> InvoiceMemoResponse:
        return InvoiceMemoResponse(memo=_invoice_memo(_decode_bolt11(request.bolt11)))

    @extension_api_method(
        method_id="utils.lightning.verify_preimage",
        namespace="utils.lightning",
        name="Verify Lightning preimage",
        host_interface="utils-lightning",
        host_name="verify_preimage",
        sdk_name="verifyPreimage",
        description="Verify that a preimage matches a payment hash.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def verify_preimage(
        self, request: VerifyPreimageRequest
    ) -> VerifyPreimageResponse:
        from lnbits.utils.crypto import verify_preimage

        return VerifyPreimageResponse(
            valid=verify_preimage(request.preimage, request.payment_hash)
        )

    @extension_api_method(
        method_id="utils.lightning.random_secret_and_hash",
        namespace="utils.lightning",
        name="Random Lightning secret and hash",
        host_interface="utils-lightning",
        host_name="random_secret_and_hash",
        sdk_name="randomSecretAndHash",
        description="Create a random secret and matching SHA256 hash.",
        required_permission="utils.basic",
        require_auth=False,
    )
    async def random_secret_and_hash(
        self, request: RandomSecretAndHashRequest
    ) -> RandomSecretAndHashResponse:
        from lnbits.utils.crypto import random_secret_and_hash

        secret, payment_hash = random_secret_and_hash(request.length)
        return RandomSecretAndHashResponse(secret=secret, hash=payment_hash)


def extension_api_utils_method_classes() -> dict[str, type[_ExtensionAPIUtilsGroup]]:
    return {
        "utils.currencies": ExtensionCurrencyUtils,
        "utils.server": ExtensionServerUtils,
        "utils.lightning": ExtensionLightningUtils,
    }


def _decode_bolt11(payment_request: str) -> Any:
    from lnbits import bolt11

    return bolt11.decode(payment_request)


def _decoded_invoice_response(invoice: Any) -> DecodeInvoiceResponse:
    return DecodeInvoiceResponse(
        payment_hash=str(getattr(invoice, "payment_hash", "")) or None,
        amount_msat=_invoice_amount_msat(invoice),
        expiry=_invoice_expiry(invoice),
        expires_at=_invoice_expires_at(invoice),
        memo=_invoice_memo(invoice),
    )


def _invoice_amount_msat(invoice: Any) -> int | None:
    amount_msat = getattr(invoice, "amount_msat", None)
    if amount_msat is None:
        return None
    return int(amount_msat)


def _invoice_expiry(invoice: Any) -> int | None:
    expiry = getattr(invoice, "expiry", None)
    if expiry is None:
        return None
    return int(expiry)


def _invoice_expires_at(invoice: Any) -> int | None:
    expiry_date = getattr(invoice, "expiry_date", None)
    if isinstance(expiry_date, datetime):
        return int(expiry_date.timestamp())

    date = getattr(invoice, "date", None)
    expiry = getattr(invoice, "expiry", None)
    if isinstance(date, datetime) and expiry is not None:
        return int(date.timestamp() + int(expiry))
    if isinstance(date, (int, float)) and expiry is not None:
        return int(date + int(expiry))
    return None


def _invoice_memo(invoice: Any) -> str | None:
    memo = getattr(invoice, "description", None)
    return str(memo) if memo is not None else None
