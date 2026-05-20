import json

from fastapi import APIRouter, Request
from loguru import logger

from lnbits.core.crud.payments import (
    get_payments,
    get_standalone_payment,
    update_payment,
)
from lnbits.core.models import Payment, PaymentFilters
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.services.fiat_providers import (
    check_fiat_status,
    check_revolut_signature,
    check_square_signature,
    check_stripe_signature,
    verify_paypal_webhook,
)
from lnbits.core.services.payments import (
    create_fiat_invoice,
    create_wallet_invoice,
    service_fee_fiat,
)
from lnbits.db import Filter, Filters
from lnbits.fiat import get_fiat_provider
from lnbits.fiat.base import FiatSubscriptionPaymentOptions
from lnbits.fiat.revolut import RevolutWallet
from lnbits.fiat.square import SquareWallet
from lnbits.settings import settings

callback_router = APIRouter(prefix="/api/v1/callback", tags=["callback"])


@callback_router.post("/{provider_name}")
async def api_generic_webhook_handler(
    provider_name: str, request: Request
) -> SimpleStatus:
    logger.info(f"Received callback from provider: '{provider_name}'.")
    if provider_name.lower() == "stripe":
        payload = await request.body()
        sig_header = request.headers.get("Stripe-Signature")
        check_stripe_signature(
            payload, sig_header, settings.stripe_webhook_signing_secret
        )
        event = await request.json()
        await handle_stripe_event(event)

        return SimpleStatus(
            success=True,
            message=f"Callback received successfully from '{provider_name}'.",
        )

    if provider_name.lower() == "paypal":
        payload = await request.body()
        await verify_paypal_webhook(request.headers, payload)
        event = await request.json()
        await handle_paypal_event(event)

        return SimpleStatus(
            success=True,
            message=f"Callback received successfully from '{provider_name}'.",
        )

    if provider_name.lower() == "square":
        payload = await request.body()
        sig_header = request.headers.get("x-square-hmacsha256-signature")
        check_square_signature(
            payload,
            sig_header,
            settings.square_webhook_signature_key,
            settings.square_payment_webhook_url,
        )
        event = await request.json()
        await handle_square_event(event)

        return SimpleStatus(
            success=True,
            message=f"Callback received successfully from '{provider_name}'.",
        )

    if provider_name.lower() == "revolut":
        payload = await request.body()
        sig_header = request.headers.get("Revolut-Signature")
        timestamp_header = request.headers.get("Revolut-Request-Timestamp")
        check_revolut_signature(
            payload,
            sig_header,
            timestamp_header,
            settings.revolut_webhook_signing_secret,
        )
        event = await request.json()
        await handle_revolut_event(event)

        return SimpleStatus(
            success=True,
            message=f"Callback received successfully from '{provider_name}'.",
        )

    return SimpleStatus(
        success=False,
        message=f"Unknown fiat provider '{provider_name}'.",
    )


async def handle_stripe_event(event: dict):
    event_id = event.get("id")
    event_type = event.get("type")
    if event_type == "checkout.session.completed":
        await _handle_stripe_checkout_session_completed(event)
    elif event_type == "payment_intent.succeeded":
        await _handle_stripe_intent_session_completed(event)
    elif event_type == "invoice.paid":
        await _handle_stripe_subscription_invoice_paid(event)
    else:
        logger.info(
            f"Unhandled Stripe event type: '{event_type}'." f" Event ID: '{event_id}'."
        )


async def _handle_stripe_intent_session_completed(event: dict):
    event_id = event.get("id")
    event_object = event.get("data", {}).get("object", {})
    object_type = event_object.get("object")
    payment_hash = event_object.get("metadata", {}).get("payment_hash")
    logger.debug(
        f"Handling Stripe event: '{event_id}'. Type: '{object_type}'."
        f" Payment hash: '{payment_hash}'."
    )
    if not payment_hash:
        logger.warning("Stripe event does not contain a payment hash.")
        return

    payment = await get_standalone_payment(payment_hash)
    if not payment:
        logger.warning(f"No payment found for hash: '{payment_hash}'.")
        return
    await check_fiat_status(payment)


async def _handle_stripe_checkout_session_completed(event: dict):
    event_id = event.get("id")
    event_object = event.get("data", {}).get("object", {})
    object_type = event_object.get("object")
    payment_hash = event_object.get("metadata", {}).get("payment_hash")
    alan_action = event_object.get("metadata", {}).get("alan_action")
    logger.debug(
        f"Handling Stripe event: '{event_id}'. Type: '{object_type}'."
        f" Payment hash: '{payment_hash}'."
    )
    if alan_action != "invoice":
        logger.warning(f"Stripe event is not an invoice: '{alan_action}'.")
        return

    if not payment_hash:
        raise ValueError("Stripe event does not contain a payment hash.")

    payment = await get_standalone_payment(payment_hash)
    if not payment:
        raise ValueError(f"No payment found for hash: '{payment_hash}'.")
    await check_fiat_status(payment)


async def _handle_stripe_subscription_invoice_paid(event: dict):
    invoice = event.get("data", {}).get("object", {})
    parent = invoice.get("parent", {})

    currency = invoice.get("currency", "").upper()
    if not currency:
        raise ValueError("Stripe invoice.paid event missing 'currency'.")

    amount_paid = invoice.get("amount_paid")
    if not amount_paid:
        raise ValueError("Stripe invoice.paid event missing 'amount_paid'.")

    payment_options = await _get_stripe_subscription_payment_options(parent)
    if not payment_options.wallet_id:
        raise ValueError("Stripe invoice.paid event missing 'wallet_id' in metadata.")

    memo = " | ".join(
        [i.get("description", "") for i in invoice.get("lines", {}).get("data", [])]
        + [payment_options.memo or "", invoice.get("customer_email", "")]
    )

    extra = {
        **(payment_options.extra or {}),
        "fiat_method": "subscription",
        "tag": payment_options.tag,
        "subscription": {
            "checking_id": invoice.get("id"),
            "payment_request": invoice.get("hosted_invoice_url"),
        },
    }

    payment = await create_fiat_invoice(
        wallet_id=payment_options.wallet_id,
        invoice_data=CreateInvoice(
            unit=currency,
            amount=amount_paid / 100,  # convert cents to dollars
            memo=memo,
            extra=extra,
            fiat_provider="stripe",
        ),
    )

    await check_fiat_status(payment)


async def _get_stripe_subscription_payment_options(
    parent: dict,
) -> FiatSubscriptionPaymentOptions:
    if not parent or not parent.get("type") == "subscription_details":
        raise ValueError("Stripe invoice.paid event does not contain a subscription.")

    metadata = parent.get("subscription_details", {}).get("metadata", {})

    if metadata.get("alan_action") != "subscription":
        raise ValueError("Stripe invoice.paid metadata action is not 'subscription'.")

    if "extra" in metadata:
        try:
            metadata["extra"] = json.loads(metadata["extra"])
        except json.JSONDecodeError as exc:
            logger.warning(exc)
            metadata["extra"] = {}

    return FiatSubscriptionPaymentOptions(**metadata)


async def handle_paypal_event(event: dict):
    event_id = event.get("id", "")
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})
    logger.info(f"Handling PayPal event: '{event_id}'. Type: '{event_type}'.")

    if event_type in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
        payment_hash = _paypal_extract_payment_hash(resource)
        if not payment_hash:
            logger.warning("PayPal event missing payment hash.")
            return
        payment = await get_standalone_payment(payment_hash)
        if not payment:
            logger.warning(f"No payment found for hash: '{payment_hash}'.")
            return
        await check_fiat_status(payment)
        return

    if event_type in ("PAYMENT.SALE.COMPLETED"):
        await _handle_paypal_subscription_payment(resource)
        return

    logger.warning(f"Unhandled PayPal event type: '{event_type}'.")


async def _handle_paypal_subscription_payment(resource: dict):
    amount_info = resource.get("amount") or {}
    currency = (amount_info.get("currency") or "").upper()
    total = amount_info.get("total")
    if not currency or total is None:
        raise ValueError("PayPal subscription event missing amount.")

    custom_id = resource.get("custom_id") or resource.get("custom")
    if not custom_id:
        raise ValueError("PayPal subscription event missing custom metadata.")

    payment_options = _deserialize_paypal_metadata(custom_id)
    if not payment_options.wallet_id:
        raise ValueError("PayPal subscription event missing wallet_id.")

    memo = payment_options.memo or ""
    extra = {
        **(payment_options.extra or {}),
        "subscription_request_id": resource.get("billing_agreement_id"),
        "fiat_method": "subscription",
        "tag": payment_options.tag,
        "subscription": {
            "checking_id": resource.get("id") or resource.get("billing_agreement_id"),
            "payment_request": "",
        },
    }

    payment = await create_fiat_invoice(
        wallet_id=payment_options.wallet_id,
        invoice_data=CreateInvoice(
            unit=currency,
            amount=float(total),
            memo=memo,
            extra=extra,
            fiat_provider="paypal",
        ),
    )

    await check_fiat_status(payment)


def _paypal_extract_payment_hash(resource: dict) -> str | None:
    purchase_units = resource.get("purchase_units") or []
    for pu in purchase_units:
        if pu.get("invoice_id"):
            return pu.get("invoice_id")
        if pu.get("custom_id"):
            return pu.get("custom_id")
    return None


def _deserialize_paypal_metadata(custom_id: str) -> FiatSubscriptionPaymentOptions:
    try:
        meta = json.loads(custom_id)
        wallet_id = meta[0] if len(meta) > 0 else None
        tag = meta[1] if len(meta) > 1 else None
        subscription_request_id = meta[2] if len(meta) > 2 else None
        extra_link = meta[3] if len(meta) > 3 else None
        memo = meta[4] if len(meta) > 4 else None

        extra = {
            "link": extra_link,
            "subscription_request_id": subscription_request_id,
        }

        return FiatSubscriptionPaymentOptions(
            wallet_id=wallet_id,
            tag=tag,
            subscription_request_id=subscription_request_id,
            extra=extra,
            memo=memo,
        )
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Failed to deserialize PayPal metadata: {e}")
        return FiatSubscriptionPaymentOptions()


async def handle_square_event(event: dict):
    event_id = event.get("event_id") or event.get("id", "")
    event_type = event.get("type", "")
    logger.info(f"Handling Square event: '{event_id}'. Type: '{event_type}'.")

    if event_type == "payment.updated":
        await _handle_square_payment_event(event)
        return

    if event_type == "invoice.payment_made":
        await _handle_square_invoice_payment_made(event)
        return

    logger.warning(f"Unhandled Square event type: '{event_type}'.")


async def handle_revolut_event(event: dict):
    event_type = event.get("event", "")
    order_id = event.get("order_id")
    logger.info(f"Handling Revolut event: '{event_type}'. Order ID: '{order_id}'.")

    if event_type in ["ORDER_AUTHORISED", "ORDER_COMPLETED"]:
        if not order_id:
            logger.warning("Revolut event missing order_id.")
            return

        payment = await get_standalone_payment(f"fiat_revolut_order_{order_id}")
        if not payment:
            logger.warning(f"No payment found for Revolut order: '{order_id}'.")
            return

        await check_fiat_status(payment)
        return

    if event_type == "SUBSCRIPTION_INITIATED":
        await _handle_revolut_subscription_initiated(event)
        return

    if event_type in [
        "SUBSCRIPTION_CANCELLED",
        "SUBSCRIPTION_FINISHED",
        "SUBSCRIPTION_OVERDUE",
    ]:
        logger.info(f"Revolut subscription lifecycle event received: '{event_type}'.")
        return

    logger.warning(f"Unhandled Revolut event type: '{event_type}'.")


async def _handle_revolut_subscription_initiated(event: dict):
    subscription_id = event.get("subscription_id")
    if not subscription_id:
        logger.warning("Revolut subscription event missing subscription_id.")
        return

    fiat_provider = await get_fiat_provider("revolut")
    if not isinstance(fiat_provider, RevolutWallet):
        logger.warning("Revolut fiat provider is not configured.")
        return

    subscription = await fiat_provider.get_subscription(subscription_id)
    reference = fiat_provider.deserialize_subscription_reference(
        subscription.get("external_reference")
    )
    if not reference:
        logger.warning("Revolut subscription event missing LNbits metadata.")
        return

    cycle_id = subscription.get("current_cycle_id")
    if not cycle_id:
        logger.warning("Revolut subscription missing current_cycle_id.")
        return

    cycle = await fiat_provider.get_subscription_cycle(subscription_id, cycle_id)
    order_id = cycle.get("order_id")
    if not order_id:
        logger.warning("Revolut subscription cycle missing order_id.")
        return

    existing_payment = await get_standalone_payment(f"fiat_revolut_order_{order_id}")
    if existing_payment:
        if existing_payment.external_id != subscription_id:
            existing_payment.external_id = subscription_id
            await update_payment(existing_payment)
        await check_fiat_status(existing_payment)
        return

    order = await fiat_provider.get_order(order_id)
    amount_minor = order.get("amount")
    currency = (order.get("currency") or "").upper()
    if amount_minor is None or not currency:
        raise ValueError("Revolut subscription order missing amount or currency.")

    extra = {
        **(reference.extra or {}),
        "subscription_request_id": reference.subscription_request_id,
        "fiat_method": "subscription",
        "tag": reference.tag,
        "subscription": {
            "checking_id": f"order_{order_id}",
            "payment_request": order.get("checkout_url") or "",
        },
    }
    lnbits_payment = await _create_revolut_subscription_payment(
        wallet_id=reference.wallet_id,
        amount_minor=amount_minor,
        currency=currency,
        memo=reference.memo or "",
        extra=extra,
        order_id=order_id,
        payment_request=order.get("checkout_url") or "",
        subscription_id=subscription_id,
    )

    await check_fiat_status(lnbits_payment)


async def _create_revolut_subscription_payment(
    wallet_id: str,
    amount_minor: int,
    currency: str,
    memo: str,
    extra: dict,
    order_id: str,
    payment_request: str,
    subscription_id: str,
) -> Payment:
    amount = RevolutWallet.minor_units_to_amount(amount_minor, currency)
    payment = await create_wallet_invoice(
        wallet_id,
        CreateInvoice(
            unit=currency,
            amount=amount,
            memo=memo,
            extra=extra,
            internal=True,
            external_id=subscription_id,
        ),
    )
    payment.fee = -abs(service_fee_fiat(payment.msat, "revolut"))
    payment.fiat_provider = "revolut"
    payment.extra["fiat_checking_id"] = f"order_{order_id}"
    payment.extra["fiat_payment_request"] = payment_request
    checking_id = f"fiat_revolut_order_{order_id}"
    await update_payment(payment, checking_id)
    payment.checking_id = checking_id
    return payment


async def _handle_square_payment_event(event: dict):
    payment = _square_extract_payment(event)
    payment_options = _deserialize_square_metadata(_square_payment_note(payment))
    if payment_options.wallet_id:
        if not _square_payment_is_completed(payment):
            logger.debug("Square subscription payment is not completed yet.")
            return
        await _handle_square_subscription_payment(payment, payment_options)
        return

    order_id = payment.get("order_id")
    if not order_id:
        logger.warning("Square payment event missing order_id.")
        return

    lnbits_payment = await get_standalone_payment(f"fiat_square_order_{order_id}")
    if not lnbits_payment:
        logger.warning(f"No payment found for Square order: '{order_id}'.")
        return

    await check_fiat_status(lnbits_payment)


async def _handle_square_invoice_payment_made(event: dict):
    invoice = event.get("data", {}).get("object", {}).get("invoice") or {}
    order_id = invoice.get("order_id")
    if not order_id:
        logger.warning("Square invoice.payment_made event missing order_id.")
        return
    subscription_id = invoice.get("subscription_id")

    fiat_provider = await get_fiat_provider("square")
    if not isinstance(fiat_provider, SquareWallet):
        logger.warning("Square fiat provider is not configured.")
        return

    payment = await fiat_provider.get_payment_for_order(order_id)
    if not payment:
        logger.warning(f"No Square payment found for invoice order: '{order_id}'.")
        return

    payment_options = _deserialize_square_metadata(_square_payment_note(payment))
    if not payment_options.wallet_id:
        payment_id = payment.get("id")
        stored_payment = (
            await get_standalone_payment(f"fiat_square_payment_{payment_id}")
            if payment_id
            else None
        )
        if not stored_payment and subscription_id:
            stored_payments = await get_payments(
                filters=Filters(
                    filters=[
                        Filter.parse_query(
                            "external_id", [subscription_id], PaymentFilters
                        )
                    ],
                    model=PaymentFilters,
                    sortby="created_at",
                    direction="desc",
                    limit=1,
                )
            )
            stored_payment = stored_payments[0] if stored_payments else None
        if stored_payment:
            payment_options = _square_payment_options_from_payment(stored_payment)
        else:
            logger.warning("Square subscription payment missing LNbits metadata.")
            return

    await _handle_square_subscription_payment(
        payment,
        payment_options,
        invoice.get("public_url") or "",
        square_subscription_id=subscription_id,
    )


async def _handle_square_subscription_payment(
    payment: dict,
    payment_options: FiatSubscriptionPaymentOptions,
    payment_request: str = "",
    square_subscription_id: str | None = None,
):
    amount_money = payment.get("amount_money") or {}
    amount = amount_money.get("amount")
    currency = (amount_money.get("currency") or "").upper()
    payment_id = payment.get("id")
    if amount is None or not currency or not payment_id:
        raise ValueError("Square subscription payment event missing payment amount.")
    wallet_id = payment_options.wallet_id
    if not wallet_id:
        raise ValueError("Square subscription payment event missing wallet_id.")

    checking_id = f"payment_{payment_id}"
    existing_payment = await get_standalone_payment(f"fiat_square_{checking_id}")
    if existing_payment:
        if (
            square_subscription_id
            and existing_payment.external_id != square_subscription_id
        ):
            existing_payment.external_id = square_subscription_id
            await update_payment(existing_payment)
        await check_fiat_status(existing_payment)
        return

    square_subscription_id = square_subscription_id or (
        payment_options.extra or {}
    ).get("square_subscription_id")
    extra = {
        **(payment_options.extra or {}),
        "subscription_request_id": payment_options.subscription_request_id,
        "fiat_method": "subscription",
        "tag": payment_options.tag,
        "subscription": {
            "checking_id": checking_id,
            "payment_request": payment_request,
        },
    }

    lnbits_payment = await create_fiat_invoice(
        wallet_id=wallet_id,
        invoice_data=CreateInvoice(
            unit=currency,
            amount=amount / 100,
            memo=payment_options.memo or "",
            extra=extra,
            fiat_provider="square",
            external_id=square_subscription_id,
        ),
    )

    await check_fiat_status(lnbits_payment)


def _square_payment_options_from_payment(
    payment: Payment,
) -> FiatSubscriptionPaymentOptions:
    extra = payment.extra or {}
    return FiatSubscriptionPaymentOptions(
        wallet_id=payment.wallet_id,
        tag=extra.get("tag") or payment.tag,
        subscription_request_id=extra.get("subscription_request_id"),
        extra=extra,
        memo=payment.memo,
    )


def _square_extract_payment(event: dict) -> dict:
    event_object = event.get("data", {}).get("object", {})
    return event_object.get("payment") or event_object


def _square_payment_is_completed(payment: dict) -> bool:
    return (payment.get("status") or "").upper() == "COMPLETED"


def _square_payment_note(payment: dict) -> str:
    return payment.get("note") or payment.get("payment_note") or ""


def _deserialize_square_metadata(custom_id: str) -> FiatSubscriptionPaymentOptions:
    try:
        meta = json.loads(custom_id)
        if not isinstance(meta, list):
            return FiatSubscriptionPaymentOptions()
        wallet_id = meta[0] if len(meta) > 0 else None
        tag = meta[1] if len(meta) > 1 else None
        subscription_request_id = meta[2] if len(meta) > 2 else None
        extra_link = meta[3] if len(meta) > 3 else None
        memo = meta[4] if len(meta) > 4 else None

        extra = {
            "link": extra_link,
            "subscription_request_id": subscription_request_id,
        }

        return FiatSubscriptionPaymentOptions(
            wallet_id=wallet_id,
            tag=tag,
            subscription_request_id=subscription_request_id,
            extra=extra,
            memo=memo,
        )
    except (json.JSONDecodeError, IndexError, TypeError):
        return FiatSubscriptionPaymentOptions()
