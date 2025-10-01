import json

from fastapi import APIRouter, Request
from loguru import logger

from lnbits.core.crud.payments import (
    get_standalone_payment,
    update_payment,
)
from lnbits.core.models import PaymentState
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.payments import CreateInvoice
from lnbits.core.services.fiat_providers import (
    check_stripe_signature,
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
        # print("### stripe webhook payload", payload)
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

    return SimpleStatus(
        success=False,
        message=f"Unknown fiat provider '{provider_name}'.",
    )


async def handle_stripe_event(event: dict):
    print("### stripe event", event)
    event_id = event.get("id")
    event_type = event.get("type")
    if event_type == "checkout.session.completed":
        # todo: parent subscriptin
        await _handle_stripe_checkout_session_completed(event)
    elif event_type == "invoice.paid":
        await _handle_stripe_subscription_invoice_paid(event)
    else:
        logger.info(
            f"Unhandled Stripe event type: '{event_type}'." f" Event ID: '{event_id}'."
        )


async def _handle_stripe_checkout_session_completed(event: dict):
    event_id = event.get("id")
    event_object = event.get("data", {}).get("object", {})
    object_type = event_object.get("object")
    payment_hash = event_object.get("metadata", {}).get("payment_hash")
    logger.debug(
        f"Handling Stripe event: '{event_id}'. Type: '{object_type}'."
        f" Payment hash: '{payment_hash}'."
    )
    if not payment_hash:
        # todo: add explicit action flag to metadata
        logger.warning("Stripe event does not contain a payment hash.")
        return

    payment = await get_standalone_payment(payment_hash)
    if not payment:
        logger.warning(f"No payment found for hash: '{payment_hash}'.")
        return
    await payment.check_fiat_status()


async def _handle_stripe_subscription_invoice_paid(event: dict):
    invoice = event.get("data", {}).get("object", {})
    parent = invoice.get("parent", {})

    payment_options = await _get_stripe_subscription_payment_options(parent)

    print("### payment_options", payment_options)
    if not payment_options:
        raise ValueError("Failed to get payment options from Stripe invoice.")

    currency = invoice.get("currency", "").upper()
    if not currency:
        raise ValueError("Stripe invoice.paid event missing currency.")

    amount_paid = invoice.get("amount_paid")
    if not amount_paid:
        raise ValueError("Stripe invoice.paid event missing amount_paid.")

    if not payment_options.wallet_id:
        raise ValueError("Stripe invoice.paid event missing wallet_id in metadata.")

    payment = await create_fiat_invoice(
        wallet_id=payment_options.wallet_id,
        invoice_data=CreateInvoice(
            unit=currency,
            amount=amount_paid / 100,  # convert cents to dollars
            memo=payment_options.memo,
            extra={
                **(payment_options.extra or {}),
                "fiat_method": "subscription",
                "tag": payment_options.tag,
                "subscription": {
                    "checking_id": invoice.get("id"),
                    "payment_request": invoice.get("hosted_invoice_url"),
                },
            },
            fiat_provider="stripe",
        ),
    )

    payment.status = PaymentState.SUCCESS
    payment.extra.pop("subscription", None)
    await update_payment(payment)


async def _get_stripe_subscription_payment_options(
    parent: dict,
) -> FiatSubscriptionPaymentOptions | None:
    if not parent or not parent.get("type") == "subscription_details":
        logger.warning("Stripe invoice.paid event does not contain a subscription.")
        return None
    metadata = parent.get("subscription_details", {}).get("metadata", {})

    if metadata.get("lnbits_action") != "subscription":
        logger.warning("Stripe invoice.paid metadata action is not 'subscription'.")
        return None
    print("### metadata 1", metadata)
    if "extra" in metadata:
        try:
            metadata["extra"] = json.loads(metadata["extra"])
        except json.JSONDecodeError as exc:
            logger.warning(exc)
            metadata["extra"] = {}
    print("### metadata 2", metadata)
    return FiatSubscriptionPaymentOptions(**metadata)
