from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key

from . import scrub_ext
from .crud import (
    create_scrub_link,
    delete_scrub_link,
    get_scrub_link,
    get_scrub_links,
    unique_scrubed_wallet,
    update_scrub_link,
)
from .models import CreateScrubLink


@scrub_ext.get("/api/v1/links", status_code=HTTPStatus.OK)
async def api_links(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    try:
        return [link.dict() for link in await get_scrub_links(wallet_ids)]

    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No SCRUB links made yet",
        )


@scrub_ext.get("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_link_retrieve(
    r: Request, link_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    link = await get_scrub_link(link_id)

    if not link:
        raise HTTPException(
            detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
        )

    return link


@scrub_ext.post("/api/v1/links", status_code=HTTPStatus.CREATED)
@scrub_ext.put("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_scrub_create_or_update(
    data: CreateScrubLink,
    link_id=None,
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    if link_id:
        link = await get_scrub_link(link_id)

        if not link:
            raise HTTPException(
                detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
            )

        if link.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
            )

        link = await update_scrub_link(**data.dict(), link_id=link_id)
    else:
        wallet_has_scrub = await unique_scrubed_wallet(wallet_id=data.wallet)
        if wallet_has_scrub > 0:
            raise HTTPException(
                detail="Wallet is already being Scrubbed",
                status_code=HTTPStatus.FORBIDDEN,
            )
        link = await create_scrub_link(data=data)

    return link


@scrub_ext.delete("/api/v1/links/{link_id}")
async def api_link_delete(link_id, wallet: WalletTypeInfo = Depends(require_admin_key)):
    link = await get_scrub_link(link_id)

    if not link:
        raise HTTPException(
            detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_scrub_link(link_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)
