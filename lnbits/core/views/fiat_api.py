from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin, check_user_exists
from lnbits.fiat import StripeWallet, get_fiat_provider
from lnbits.fiat.base import CreateFiatSubscription

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")


@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)


@fiat_router.post(
    "/{provider}/subscription",
    status_code=HTTPStatus.OK,
)
async def create_subscription(
    provider: str, data: CreateFiatSubscription, user=Depends(check_user_exists)
):
    fiat_provider = await get_fiat_provider(provider)
    if not fiat_provider:
        raise HTTPException(status_code=404, detail="Fiat provider not found")

    if not user.admin:
        if data.payment_options.tag or data.payment_options.extra:
            raise HTTPException(
                status_code=403,
                detail="Only admins can set tag or extra for subscription payments",
            )

    resp = await fiat_provider.create_subscription(
        data.subscription_id, data.quantity, data.payment_options
    )
    print("### resp", resp)
    return {"status": resp.checkout_session_url}


@fiat_router.post(
    "/{provider}/connection_token",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def connection_token(provider: str):
    fiat_provider = await get_fiat_provider(provider)
    if provider == "stripe":
        if not isinstance(fiat_provider, StripeWallet):
            raise HTTPException(
                status_code=500, detail="Stripe wallet/provider not configured"
            )
        try:
            tok = await fiat_provider.create_terminal_connection_token()
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
