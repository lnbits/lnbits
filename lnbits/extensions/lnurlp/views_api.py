from typing import Optional
from fastapi.param_functions import Query
from pydantic.main import BaseModel
from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.utils.exchange_rates import currencies, get_fiat_rate_satoshis

from . import lnurlp_ext
from .crud import (
    create_pay_link,
    get_pay_link,
    get_pay_links,
    update_pay_link,
    delete_pay_link,
)

@lnurlp_ext.get("/api/v1/currencies")
async def api_list_currencies_available():
    return jsonify(list(currencies.keys()))


@lnurlp_ext.get("/api/v1/links")
@api_check_wallet_key("invoice")
async def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    try:
        return (
                [
                    {**link._asdict(), **{"lnurl": link.lnurl}}
                    for link in await get_pay_links(wallet_ids)
                ],
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                },
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlp_ext.get("/api/v1/links/<link_id>")
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_pay_link(link_id)

    if not link:
        return {"message": "Pay link does not exist."}, HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return {"message": "Not your pay link."}, HTTPStatus.FORBIDDEN

    return {**link._asdict(), **{"lnurl": link.lnurl}}, HTTPStatus.OK

class CreateData(BaseModel):
    description:  str
    min:  int = Query(0.01, ge=0.01)
    max:  int = Query(0.01, ge=0.01)
    currency:  Optional[str] 
    comment_chars:  int = Query(0, ge=0, lt=800) 
    webhook_url:  Optional[str] 
    success_text:  Optional[str] 
    success_url:  Optional[str] 

@lnurlp_ext.post("/api/v1/links")
@lnurlp_ext.put("/api/v1/links/<link_id>")
@api_check_wallet_key("invoice")
async def api_link_create_or_update(data: CreateData, link_id=None):
    if data.min > data.max:
        return {"message": "Min is greater than max."}, HTTPStatus.BAD_REQUEST

    if data.currency == None and (
        round(data.min) != data.min or round(data.max) != data.max
    ):
        return {"message": "Must use full satoshis."}, HTTPStatus.BAD_REQUEST

    if "success_url" in data and data.success_url[:8] != "https://":
        return (
            {"message": "Success URL must be secure https://..."},
            HTTPStatus.BAD_REQUEST,
        )

    if link_id:
        link = await get_pay_link(link_id)

        if not link:
            return (
                {"message": "Pay link does not exist."},
                HTTPStatus.NOT_FOUND,
            )

        if link.wallet != g.wallet.id:
            return {"message": "Not your pay link."}, HTTPStatus.FORBIDDEN

        link = await update_pay_link(link_id, **data)
    else:
        link = await create_pay_link(wallet_id=g.wallet.id, **data)

    return (
        {**link._asdict(), **{"lnurl": link.lnurl}},
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@lnurlp_ext.delete("/api/v1/links/<link_id>")
@api_check_wallet_key("invoice")
async def api_link_delete(link_id):
    link = await get_pay_link(link_id)

    if not link:
        return {"message": "Pay link does not exist."}, HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return {"message": "Not your pay link."}, HTTPStatus.FORBIDDEN

    await delete_pay_link(link_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlp_ext.get("/api/v1/rate/<currency>")
async def api_check_fiat_rate(currency):
    try:
        rate = await get_fiat_rate_satoshis(currency)
    except AssertionError:
        rate = None

    return {"rate": rate}, HTTPStatus.OK
