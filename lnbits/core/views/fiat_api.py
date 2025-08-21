from http import HTTPStatus
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin
from lnbits.settings import settings
from lnbits.fiat.stripe import StripeTerminalService

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")


@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)

def get_terminal_service() -> StripeTerminalService:
    api_key = settings.stripe_api_secret_key
    if not api_key:
        raise HTTPException(500, "Stripe secret key not configured")
    return StripeTerminalService(api_key=api_key)

class CreatePIBody(BaseModel):
    amount: int = Field(..., ge=1, description="Minor units, e.g. $1 => 100")
    currency: str = Field("usd", min_length=3, max_length=3)
    payment_hash: Optional[str] = None
    order_id: Optional[str] = None

@fiat_router.post(
        "/stripe/terminal/connection_token",
        status_code=HTTPStatus.OK,
        dependencies=[Depends(check_admin)],
)
async def stripe_terminal_connection_token(
    svc: StripeTerminalService = Depends(get_terminal_service),
):
    try:
        tok = await svc.create_connection_token(location_id=None)
        return {"secret": tok["secret"]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    finally:
        await svc.aclose()


@fiat_router.post(
        "/stripe/terminal/payment_intents", 
        status_code=HTTPStatus.OK,
        dependencies=[Depends(check_admin)],
)
async def stripe_terminal_create_payment_intent(
    body: CreatePIBody, svc: StripeTerminalService = Depends(get_terminal_service)
):
    try:
        pi = await svc.create_card_present_payment_intent(
            amount=body.amount,
            currency=body.currency.lower(),
            lnbits_payment_hash=body.payment_hash or "",
            lnbits_order_id=body.order_id or "",
            source="android_tap_to_pay",
        )
        return {"id": pi["id"], "client_secret": pi["client_secret"]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    finally:
        await svc.aclose()