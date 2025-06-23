from fastapi import APIRouter, Request

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import (
    check_stripe_signature,
    handle_stripe_event,
)
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

    return SimpleStatus(
        success=False,
        message=f"Unknown fiat provider '{provider_name}'.",
    )
