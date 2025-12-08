import json

from fastapi import APIRouter, Request
from loguru import logger

from lnbits.core.crud.payments import (
    get_standalone_payment,
)
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.services.fiat_providers import (
    check_stripe_signature,
    verify_paypal_webhook,
)
from lnbits.core.services.payments import create_fiat_invoice
from lnbits.fiat.base import FiatSubscriptionPaymentOptions
from lnbits.settings import settings

callback_router = APIRouter(prefix="/api/v1/callback", tags=["callback"])


@callback_router.post("/{provider_name}")
async def api_generic_webhook_handler(
    provider_name: str, request: Request
) -> SimpleStatus:

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
    await payment.check_fiat_status()


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
    await payment.check_fiat_status()


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

    await payment.check_fiat_status()


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
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})

    if event_type in ("CHECKOUT.ORDER.APPROVED", "PAYMENT.CAPTURE.COMPLETED"):
        payment_hash = _paypal_extract_payment_hash(resource)
        if not payment_hash:
            logger.warning("PayPal event missing payment hash.")
            return
        payment = await get_standalone_payment(payment_hash)
        if not payment:
            logger.warning(f"No payment found for hash: '{payment_hash}'.")
            return
        await payment.check_fiat_status()
        return

    if event_type in (
        "PAYMENT.SALE.COMPLETED",
        "BILLING.SUBSCRIPTION.PAYMENT.SUCCEEDED",
    ):
        await _handle_paypal_subscription_payment(resource)
        return

    logger.info(f"Unhandled PayPal event type: '{event_type}'.")


async def _handle_paypal_subscription_payment(resource: dict):
    amount_info = resource.get("amount") or {}
    currency = (amount_info.get("currency_code") or "").upper()
    total = amount_info.get("value")
    if not currency or total is None:
        raise ValueError("PayPal subscription event missing amount.")

    custom_id = resource.get("custom_id") or resource.get("custom")
    if not custom_id:
        raise ValueError("PayPal subscription event missing custom metadata.")

    try:
        metadata = json.loads(custom_id)
    except json.JSONDecodeError:
        metadata = {}

    payment_options = FiatSubscriptionPaymentOptions(**metadata)
    if not payment_options.wallet_id:
        raise ValueError("PayPal subscription event missing wallet_id.")

    memo = payment_options.memo or ""
    extra = {
        **(payment_options.extra or {}),
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

    await payment.check_fiat_status()


def _paypal_extract_payment_hash(resource: dict) -> str | None:
    purchase_units = resource.get("purchase_units") or []
    for pu in purchase_units:
        if pu.get("invoice_id"):
            return pu.get("invoice_id")
        if pu.get("custom_id"):
            return pu.get("custom_id")
    return None
