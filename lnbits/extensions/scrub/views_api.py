from http import HTTPStatus

from fastapi import Request
from fastapi.param_functions import Query
from fastapi.params import Depends
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type
from lnbits.utils.exchange_rates import currencies, get_fiat_rate_satoshis

from . import scrub_ext
from .crud import (
    create_scrub_link,
    delete_scrub_link,
    get_scrub_link,
    get_scrub_links,
    update_scrub_link,
)
from .models import ScrubLink


@scrub_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


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
        return [
            {**link.dict()}
            for link in await get_pay_links(wallet_ids)
        ]

    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No SCRUB links made yet",
        )


@scrub_ext.get("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_link_retrieve(
    r: Request, link_id, wallet: WalletTypeInfo = Depends(get_key_type)
):
    link = await get_pay_link(link_id)

    if not link:
        raise HTTPException(
            detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
        )

    return {**link.dict(), **{"lnurl": link.lnurl(r)}}


@scrub_ext.post("/api/v1/links", status_code=HTTPStatus.CREATED)
@scrub_ext.put("/api/v1/links/{link_id}", status_code=HTTPStatus.OK)
async def api_link_create_or_update(
    data: ScrubLink,
    link_id=None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    print("WAH")
    if data.min < 1:
        raise HTTPException(
            detail="Min must be more than 1.", status_code=HTTPStatus.BAD_REQUEST
        )

    if data.min > data.max:
        raise HTTPException(
            detail="Min is greater than max.", status_code=HTTPStatus.BAD_REQUEST
        )

    if data.currency == None and (
        round(data.min) != data.min or round(data.max) != data.max
    ):
        raise HTTPException(
            detail="Must use full satoshis.", status_code=HTTPStatus.BAD_REQUEST
        )

    if "success_url" in data and data.success_url[:8] != "https://":
        raise HTTPException(
            detail="Success URL must be secure https://...",
            status_code=HTTPStatus.BAD_REQUEST,
        )

    if link_id:
        link = await get_pay_link(link_id)

        if not link:
            raise HTTPException(
                detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
            )

        if link.wallet != wallet.wallet.id:
            raise HTTPException(
                detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
            )

        link = await update_pay_link(**data.dict(), link_id=link_id)
    else:
        link = await create_pay_link(data, wallet_id=wallet.wallet.id)
    
    return {**link.dict(), "lnurl": link.lnurl}


@scrub_ext.delete("/api/v1/links/{link_id}")
async def api_link_delete(link_id, wallet: WalletTypeInfo = Depends(get_key_type)):
    link = await get_pay_link(link_id)

    if not link:
        raise HTTPException(
            detail="Scrub link does not exist.", status_code=HTTPStatus.NOT_FOUND
        )

    if link.wallet != wallet.wallet.id:
        raise HTTPException(
            detail="Not your pay link.", status_code=HTTPStatus.FORBIDDEN
        )

    await delete_pay_link(link_id)
    raise HTTPException(status_code=HTTPStatus.NO_CONTENT)


@scrub_ext.get("/api/v1/rate/{currency}", status_code=HTTPStatus.OK)
async def api_check_fiat_rate(currency):
    try:
        rate = await get_fiat_rate_satoshis(currency)
    except AssertionError:
        rate = None

    return {"rate": rate}
