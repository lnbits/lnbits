import base64
import json
from http import HTTPStatus
from urllib.parse import unquote, urlparse

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from loguru import logger

from lnbits.core.models import (
    CreateWebPushSubscription,
    WebPushSubscription,
)
from lnbits.core.models.users import AccountId
from lnbits.decorators import (
    check_account_id_exists,
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
    account_id: AccountId = Depends(check_account_id_exists),
) -> WebPushSubscription:
    try:
        subscription = json.loads(data.subscription)
        endpoint = subscription["endpoint"]
        host = urlparse(str(request.url)).netloc

        subscription = await get_webpush_subscription(endpoint, account_id.id)
        if subscription:
            return subscription
        else:
            return await create_webpush_subscription(
                endpoint,
                account_id.id,
                data.subscription,
                host,
            )
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Cannot create webpush notification",
        ) from exc


@webpush_router.delete("", status_code=HTTPStatus.OK)
async def api_delete_webpush_subscription(
    request: Request,
    account_id: AccountId = Depends(check_account_id_exists),
):
    try:
        endpoint = unquote(
            base64.b64decode(str(request.query_params.get("endpoint"))).decode("utf-8")
        )
        count = await delete_webpush_subscription(endpoint, account_id.id)
        return {"count": count}
    except Exception as exc:
        logger.debug(exc)
        raise HTTPException(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Cannot delete webpush notification",
        ) from exc
