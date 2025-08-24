from http import HTTPStatus

import httpx
from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin
from lnbits.fiat import StripeWallet, get_fiat_provider
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
        raise HTTPException(
            status_code=500, detail="Stripe wallet/provider not configured"
        )

    try:
        location_id = getattr(settings, "stripe_terminal_location_id", None)
        tok = await wallet.create_terminal_connection_token(location_id=location_id)
        secret = tok.get("secret")
        if not secret:
            raise HTTPException(
                status_code=502, detail="Stripe returned no connection token"
            )
        return {"secret": secret}

    except httpx.HTTPStatusError as e:
        status = (
            e.response.status_code if getattr(e, "response", None) is not None else 502
        )
        detail = e.response.text if getattr(e, "response", None) is not None else str(e)
        raise HTTPException(status_code=status, detail=detail) from e

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create connection token: {e}"
        ) from e
