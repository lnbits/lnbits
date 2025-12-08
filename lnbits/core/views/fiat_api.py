from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.wallets import WalletTypeInfo
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin, require_admin_key
from lnbits.fiat import StripeWallet, get_fiat_provider
from lnbits.fiat.base import CreateFiatSubscription, FiatSubscriptionResponse

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
    provider: str,
    data: CreateFiatSubscription,
    key_type: WalletTypeInfo = Depends(require_admin_key),
) -> FiatSubscriptionResponse:
    fiat_provider = await get_fiat_provider(provider)
    if not fiat_provider:
        raise HTTPException(404, "Fiat provider not found")

    wallet_id = data.payment_options.wallet_id

    if wallet_id and wallet_id != key_type.wallet.id:
        raise HTTPException(
            403,
            "Wallet id does not match your API key."
            "Leave it empty to use your key's wallet.",
        )

    data.payment_options.wallet_id = key_type.wallet.id
    subscription_response = await fiat_provider.create_subscription(
        data.subscription_id, data.quantity, data.payment_options
    )
    return subscription_response


@fiat_router.delete(
    "/{provider}/subscription/{subscription_id}",
    status_code=HTTPStatus.OK,
)
async def cancel_subscription(
    provider: str,
    subscription_id: str,
    key_type: WalletTypeInfo = Depends(require_admin_key),
) -> FiatSubscriptionResponse:
    fiat_provider = await get_fiat_provider(provider)
    if not fiat_provider:
        raise HTTPException(404, "Fiat provider not found")

    resp = await fiat_provider.cancel_subscription(subscription_id, key_type.wallet.id)

    return resp


@fiat_router.post(
    "/{provider}/connection_token",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def connection_token(provider: str):
    fiat_provider = await get_fiat_provider(provider)
    if not fiat_provider:
        raise HTTPException(status_code=404, detail="Fiat provider not found")

    if provider != "stripe":
        raise HTTPException(
            status_code=400,
            detail=f"Connection tokens are not supported for provider '{provider}'.",
        )

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
