from http import HTTPStatus

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from starlette.responses import RedirectResponse

from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
)

from ..crud import (
    create_tinyurl,
    delete_tinyurl,
    get_tinyurl,
    get_tinyurl_by_url,
)

tinyurl_router = APIRouter()


@tinyurl_router.post(
    "/api/v1/tinyurl",
    name="Tinyurl",
    description="creates a tinyurl",
)
async def api_create_tinyurl(
    url: str, endless: bool = False, wallet: WalletTypeInfo = Depends(get_key_type)
):
    tinyurls = await get_tinyurl_by_url(url)
    try:
        for tinyurl in tinyurls:
            if tinyurl:
                if tinyurl.wallet == wallet.wallet.inkey:
                    return tinyurl
        return await create_tinyurl(url, endless, wallet.wallet.inkey)
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Unable to create tinyurl"
        )


@tinyurl_router.get(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="get a tinyurl by id",
)
async def api_get_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
):
    try:
        tinyurl = await get_tinyurl(tinyurl_id)
        if tinyurl:
            if tinyurl.wallet == wallet.wallet.inkey:
                return tinyurl
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Unable to fetch tinyurl"
        )


@tinyurl_router.delete(
    "/api/v1/tinyurl/{tinyurl_id}",
    name="Tinyurl",
    description="delete a tinyurl by id",
)
async def api_delete_tinyurl(
    tinyurl_id: str, wallet: WalletTypeInfo = Depends(get_key_type)
):
    try:
        tinyurl = await get_tinyurl(tinyurl_id)
        if tinyurl:
            if tinyurl.wallet == wallet.wallet.inkey:
                await delete_tinyurl(tinyurl_id)
                return {"deleted": True}
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Wrong key provided."
        )
    except Exception:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="Unable to delete"
        )


@tinyurl_router.get(
    "/t/{tinyurl_id}",
    name="Tinyurl",
    description="redirects a tinyurl by id",
)
async def api_tinyurl(tinyurl_id: str):
    tinyurl = await get_tinyurl(tinyurl_id)
    if tinyurl:
        response = RedirectResponse(url=tinyurl.url)
        return response
    else:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="unable to find tinyurl"
        )
