import secrets
from datetime import datetime, timezone

from lnbits.db import Connection
from lnbits.exceptions import InvoiceError, OfferError, PaymentError
from lnbits.settings import settings
from lnbits.wallets import get_funding_source

from ..crud import create_offer as crud_create_offer
from ..crud import disable_offer as crud_disable_offer
from ..crud import enable_offer as crud_enable_offer
from ..crud import get_standalone_offer, get_wallet
from ..models import CreateOffer, Offer
from .payments import calculate_fiat_amounts


async def create_offer(
    *,
    wallet_id: str,
    memo: str,
    amount_sat: int | None = None,
    absolute_expiry: int | None = None,
    single_use: bool | None = None,
    extra: dict | None = None,
    webhook: str | None = None,
    conn: Connection | None = None,
) -> Offer:

    user_wallet = await get_wallet(wallet_id, conn=conn)
    if not user_wallet:
        raise OfferError(f"Could not fetch wallet '{wallet_id}'.", status="failed")

    offer_memo = memo[:640]

    funding_source = get_funding_source()

    # How should this be handled with offers?
    if amount_sat:
        if amount_sat <= 0:
            raise OfferError(
                "Offers with negative or zero amounts are not valid.", status="failed"
            )
        if amount_sat > settings.lnbits_max_incoming_payment_amount_sats:
            raise OfferError(
                f"Offer amount {amount_sat} sats is too high. Max allowed: "
                f"{settings.lnbits_max_incoming_payment_amount_sats} sats.",
                status="failed",
            )
        if settings.is_wallet_max_balance_exceeded(
            user_wallet.balance_msat / 1000 + amount_sat
        ):
            raise OfferError(
                f"Wallet balance cannot exceed "
                f"{settings.lnbits_wallet_limit_max_balance} sats.",
                status="failed",
            )

    while True:
        offer_resp = await funding_source.create_offer(
            amount=amount_sat,
            issuer=secrets.token_hex(8),
            memo=offer_memo,
            absolute_expiry=absolute_expiry,
            single_use=single_use,
        )

        if not offer_resp.ok or not offer_resp.invoice_offer or not offer_resp.offer_id:
            raise OfferError(
                offer_resp.error_message or "unexpected backend error.",
                status="pending",
            )

        if offer_resp.created:
            break

    create_offer_model = CreateOffer(
        amount_msat=amount_sat * 1000 if amount_sat else None,
        memo=memo,
        extra=extra,
        expiry=(
            datetime.fromtimestamp(absolute_expiry, timezone.utc)
            if absolute_expiry
            else None
        ),
        webhook=webhook,
    )

    offer = await crud_create_offer(
        offer_id=offer_resp.offer_id,
        wallet_id=wallet_id,
        bolt12=offer_resp.invoice_offer,
        data=create_offer_model,
        active=offer_resp.active,
        single_use=offer_resp.single_use,
        used=offer_resp.used,
        conn=conn,
    )

    return offer


async def enable_offer(
    *,
    wallet_id: str,
    offer_id: str,
    conn: Connection | None = None,
) -> Offer:

    offer = await get_standalone_offer(offer_id=offer_id, wallet_id=wallet_id)

    if not offer:
        raise OfferError("Could not find offer", status="error")

    if offer.active is True:
        return offer

    funding_source = get_funding_source()

    offer_resp = await funding_source.enable_offer(offer_id=offer_id)

    if not offer_resp.ok:
        raise OfferError(
            offer_resp.error_message or "unexpected backend error.", status="pending"
        )

    if offer_resp.created:

        if (
            not offer_resp.invoice_offer
            or not offer_resp.offer_id == offer_id
            or not offer_resp.active
        ):
            raise OfferError(
                offer_resp.error_message or "unexpected backend state.", status="error"
            )

        assert offer_resp.offer_id
        await crud_enable_offer(offer_resp.offer_id)

    offer.active = True
    return offer


async def disable_offer(
    *,
    wallet_id: str,
    offer_id: str,
    conn: Connection | None = None,
) -> Offer:

    offer = await get_standalone_offer(offer_id=offer_id, wallet_id=wallet_id)

    if not offer:
        raise OfferError("Could not find offer", status="error")

    if offer.active is False:
        return offer

    funding_source = get_funding_source()

    offer_resp = await funding_source.disable_offer(offer_id=offer_id)

    if not offer_resp.ok:
        raise OfferError(
            offer_resp.error_message or "unexpected backend error.", status="pending"
        )

    if offer_resp.created:

        if (
            not offer_resp.invoice_offer
            or not offer_resp.offer_id == offer_id
            or offer_resp.active
        ):
            raise OfferError(
                offer_resp.error_message or "unexpected backend state.", status="error"
            )

        assert offer_resp.offer_id
        await crud_disable_offer(offer_resp.offer_id)

    offer.active = False
    return offer


async def fetch_invoice(
    *,
    wallet_id: str,
    offer: str,
    amount: float | None = None,
    payer_note: str | None = None,
    currency: str | None = "sat",
    extra: dict | None = None,
    conn: Connection | None = None,
) -> str:

    if settings.lnbits_only_allow_incoming_payments:
        raise PaymentError("Only incoming payments allowed.", status="failed")

    user_wallet = await get_wallet(wallet_id, conn=conn)
    if not user_wallet:
        raise InvoiceError(f"Could not fetch wallet '{wallet_id}'.", status="failed")

    amount_sat = None

    if amount:

        if currency:
            amount_sat, extra = await calculate_fiat_amounts(
                amount, user_wallet, currency, extra
            )
        else:
            amount_sat = int(amount)

    funding_source = get_funding_source()

    invoice_response = await funding_source.fetch_invoice(
        offer=offer, amount=amount_sat, payer_note=payer_note
    )

    if invoice_response.failed:
        raise InvoiceError(
            (
                invoice_response.error_message
                if invoice_response.error_message
                else "Could not fetch invoice"
            ),
            status="failed",
        )
    assert invoice_response.payment_request is not None

    return invoice_response.payment_request
