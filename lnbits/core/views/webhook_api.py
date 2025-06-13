from fastapi import APIRouter, Request

from lnbits.core.services.fiat_providers import handle_stripe_event

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
