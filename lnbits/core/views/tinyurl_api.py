from http import HTTPStatus

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from starlette.responses import RedirectResponse

from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_invoice_key,
)

from ..crud import (
    create_tinyurl,
    delete_tinyurl,
    get_tinyurl,
    get_tinyurl_by_url,
)

tinyurl_router = APIRouter(tags=["Tinyurl"])


@tinyurl_router.post(
    "/api/v1/tinyurl",
    name="Tinyurl",
    description="creates a tinyurl",
)
async def api_create_tinyurl(
    url: str, endless: bool = False, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    tinyurls = await get_tinyurl_by_url(url)
    for tinyurl in tinyurls:
        if tinyurl.wallet == wallet.wallet.id:
            return tinyurl
    return await create_tinyurl(url, endless, wallet.wallet.id)


@tinyurl_router.get(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="get a tinyurl by id",
)
async def api_get_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(require_invoice_key)
):
    tinyurl = await get_tinyurl(tinyurl_id)
    if tinyurl.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    return tinyurl


@tinyurl_router.delete(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="delete a tinyurl by id",
)
async def api_delete_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    tinyurl = await get_tinyurl(tinyurl_id)
    if tinyurl.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    await delete_tinyurl(tinyurl_id)
    return {"deleted": True}


@tinyurl_router.get(
    "/t/{tinyurl_id}",
    name="Tinyurl",
    description="redirects a tinyurl by id",
)
async def api_tinyurl(tinyurl_id: str):
    tinyurl = await get_tinyurl(tinyurl_id)
    response = RedirectResponse(url=tinyurl.url)
    return response
