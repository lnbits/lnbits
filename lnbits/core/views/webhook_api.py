from fastapi import APIRouter, Request

webhook_router = APIRouter(prefix="/api/v1/webhook", tags=["Webhooks"])


@webhook_router.post("/{provider_name}")
async def api_generic_webhook_handler(provider_name: str, request: Request):
    print("### Received webhook request ###", provider_name)
    print(f"Headers: {request.headers}")
    print(f"Body: {await request.body()}")
    return {
        "status": "success",
        "message": f"Webhook received successfully from '{provider_name}'.",
    }
