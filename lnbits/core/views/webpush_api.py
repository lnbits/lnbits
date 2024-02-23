import base64
import json
from http import HTTPStatus
from urllib.parse import unquote, urlparse

from fastapi import (
    APIRouter,
    Depends,
    Request,
)

from lnbits.core.models import (
    CreateWebPushSubscription,
    WebPushSubscription,
)
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
)

from ..crud import (
    create_webpush_subscription,
    delete_webpush_subscription,
    get_webpush_subscription,
)

webpush_router = APIRouter(prefix="/api/v1/webpush", tags=["Webpush"])


@webpush_router.post("", status_code=HTTPStatus.CREATED)
async def api_create_webpush_subscription(
    request: Request,
    data: CreateWebPushSubscription,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> WebPushSubscription:
    subscription = json.loads(data.subscription)
    endpoint = subscription["endpoint"]
    host = urlparse(str(request.url)).netloc

    subscription = await get_webpush_subscription(endpoint, wallet.wallet.user)
    if subscription:
        return subscription
    else:
        return await create_webpush_subscription(
            endpoint,
            wallet.wallet.user,
            data.subscription,
            host,
        )


@webpush_router.delete("", status_code=HTTPStatus.OK)
async def api_delete_webpush_subscription(
    request: Request,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    endpoint = unquote(
        base64.b64decode(str(request.query_params.get("endpoint"))).decode("utf-8")
    )
    await delete_webpush_subscription(endpoint, wallet.wallet.user)
