from fastapi import APIRouter, Request

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import handle_stripe_event

callback_router = APIRouter(prefix="/api/v1/webhook", tags=["Webhooks"])


@callback_router.post("/{provider_name}")
async def api_generic_webhook_handler(
    provider_name: str, request: Request
) -> SimpleStatus:
    print("### Received webhook request ###", provider_name)
    print(f"Headers: {request.headers}")
    body = await request.body()
    print(f"Body: {body.decode('utf-8')}")
    if provider_name.lower() == "stripe":
        event = await request.json()
        await handle_stripe_event(event)
    return SimpleStatus(
        success=True,
        message=f"Callback received successfully from '{provider_name}'.",
    )
