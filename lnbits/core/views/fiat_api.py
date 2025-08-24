from http import HTTPStatus
import httpx
from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.fiat import get_fiat_provider, StripeWallet
from lnbits.decorators import check_admin
from lnbits.settings import settings

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")

@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)

@fiat_router.post(
    "/stripe/terminal/connection_token",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def stripe_terminal_connection_token():
    wallet = await get_fiat_provider("stripe")
    if not isinstance(wallet, StripeWallet):
        raise HTTPException(500, "Stripe wallet/provider not configured")

    try:
        location_id = getattr(settings, "stripe_terminal_location_id", None)
        tok = await wallet.create_terminal_connection_token(location_id=location_id)
        secret = tok.get("secret")
        if not secret:
            raise HTTPException(502, "Stripe returned no connection token")
        return {"secret": secret}
    except httpx.HTTPStatusError as e:
        # surface Stripe error body if present
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        raise HTTPException(500, f"Failed to create connection token: {e}")
