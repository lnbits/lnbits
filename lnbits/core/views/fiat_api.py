from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin
from lnbits.fiat import StripeWallet, get_fiat_provider

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")


@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)


@fiat_router.post(
    "/{provider}/connection_token",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def connection_token(provider: str):
    provider_wallet = await get_fiat_provider(provider)
    if provider == "stripe":
        if not isinstance(provider_wallet, StripeWallet):
            raise HTTPException(
                status_code=500, detail="Stripe wallet/provider not configured"
            )
        try:
            tok = await provider_wallet.create_terminal_connection_token()
            secret = tok.get("secret")
            if not secret:
                raise HTTPException(
                    status_code=502, detail="Stripe returned no connection token"
                )
            return {"secret": secret}
        except Exception as e:
            raise HTTPException(
                status_code=500, detail="Failed to create connection token"
            ) from e
