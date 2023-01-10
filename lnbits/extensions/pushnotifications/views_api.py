import base64
import hashlib
import json
from http import HTTPStatus
from urllib.parse import unquote, urlparse

from fastapi import Depends, Query, Request
from starlette.exceptions import HTTPException
from starlette.requests import Request

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, require_admin_key

from . import pushnotifications_ext
from .crud import (
    create_subscription,
    delete_subscriptions,
    get_subscriptions_by_endpoint,
)
from .models import CreateSubscription
from .tasks import send_push_notification


@pushnotifications_ext.post("/api/v1/subscription", status_code=HTTPStatus.CREATED)
async def api_subscription_create(
    request: Request,
    data: CreateSubscription,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    all_wallets: bool = Query(False),
):
    subscription = json.loads(data.subscription)
    endpoint = subscription["endpoint"]
    host = urlparse(str(request.url)).netloc

    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        user = await get_user(wallet.wallet.user)
        if user:
            wallet_ids = user.wallet_ids

    for wallet_id in wallet_ids:
        new_subscription = await create_subscription(
            endpoint, wallet_id, data.subscription, host
        )
        assert new_subscription, "Newly created subscription couldn't be retrieved"

    send_push_notification(new_subscription, "LNbits", "Ready for push notifications.")

    return ""


@pushnotifications_ext.delete("/api/v1/subscription", status_code=HTTPStatus.NO_CONTENT)
async def api_delete_subscription(
    request: Request, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    endpoint = unquote(
        base64.b64decode(request.query_params.get("endpoint")).decode("latin1")
    )

    if "all_wallets" in request.query_params:
        await delete_subscriptions(endpoint)

    return ""
