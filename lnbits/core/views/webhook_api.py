from fastapi import APIRouter, Request
from loguru import logger

from lnbits.core.crud.payments import get_standalone_payment

# todo: rename to callbacks_api.py
webhook_router = APIRouter(prefix="/api/v1/webhook", tags=["Webhooks"])


@webhook_router.post("/{provider_name}")
async def api_generic_webhook_handler(provider_name: str, request: Request):
    print("### Received webhook request ###", provider_name)
    print(f"Headers: {request.headers}")
    body = await request.body()
    print(f"Body: {body.decode('utf-8')}")
    if provider_name.lower() == "stripe":
        event = await request.json()
        await handle_stripe_event(event)
    return {
        "status": "success",
        "message": f"Webhook received successfully from '{provider_name}'.",
    }


async def handle_stripe_event(event: dict):
    # todo: check signature
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
