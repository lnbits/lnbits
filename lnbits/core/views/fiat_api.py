from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from lnbits.core.crud.settings import set_settings_field
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.wallets import WalletTypeInfo
from lnbits.core.services import update_cached_settings
from lnbits.core.services.fiat_providers import test_connection
from lnbits.decorators import check_admin, require_admin_key
from lnbits.fiat import RevolutWallet, StripeWallet, get_fiat_provider
from lnbits.fiat.base import CreateFiatSubscription, FiatSubscriptionResponse

fiat_router = APIRouter(tags=["Fiat API"], prefix="/api/v1/fiat")


class RevolutCreateWebhook(BaseModel):
    url: str
    endpoint: str | None = None
    api_secret_key: str | None = None
    api_version: str | None = None


class RevolutCreateWebhookResponse(BaseModel):
    id: str | None = None
    url: str
    events: list[str] = []
    signing_secret: str
    already_exists: bool = False


@fiat_router.put(
    "/check/{provider}",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_test_fiat_provider(provider: str) -> SimpleStatus:
    return await test_connection(provider)


@fiat_router.post(
    "/revolut/webhook",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(check_admin)],
)
async def api_create_revolut_webhook(
    data: RevolutCreateWebhook,
) -> RevolutCreateWebhookResponse:
    try:
        webhook = await RevolutWallet.create_webhook(
            url=data.url,
            endpoint=data.endpoint,
            api_secret_key=data.api_secret_key,
            api_version=data.api_version,
        )
    except ValueError as exc:
        logger.warning(exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=500, detail="Failed to create Revolut webhook."
        ) from exc

    signing_secret = webhook.get("signing_secret")
    webhook_url = webhook.get("url") or data.url
    if not signing_secret:
        raise HTTPException(
            status_code=502, detail="Revolut returned no webhook signing secret."
        )

    updated_settings = {
        "revolut_payment_webhook_url": webhook_url,
        "revolut_webhook_signing_secret": signing_secret,
    }
    for key, value in updated_settings.items():
        await set_settings_field(key, value)
    update_cached_settings(updated_settings)

    return RevolutCreateWebhookResponse(
        id=webhook.get("id"),
        url=webhook_url,
        events=webhook.get("events") or [],
        signing_secret=signing_secret,
        already_exists=webhook.get("already_exists", False),
    )


@fiat_router.post(
    "/{provider}/subscription",
    status_code=HTTPStatus.OK,
)
async def create_subscription(
    provider: str,
    data: CreateFiatSubscription,
    key_type: WalletTypeInfo = Depends(require_admin_key),
) -> FiatSubscriptionResponse:
    logger.debug(
        f"Creating subscription with provider '{provider}. '"
        f"Subscription ID '{data.subscription_id}'."
    )

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
    if subscription_response.error_message:
        logger.warning(
            f"Failed to create subscription with provider '{provider}': "
            f"{subscription_response.error_message}"
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
