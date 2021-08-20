from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from pydantic import BaseModel
from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder

from . import withdraw_ext
from .crud import (
    create_withdraw_link,
    get_withdraw_link,
    get_withdraw_links,
    update_withdraw_link,
    delete_withdraw_link,
    create_hash_check,
    get_hash_check,
)


@withdraw_ext.get("/api/v1/links")
@api_check_wallet_key("invoice")
async def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    try:
        return (
            jsonable_encoder(
                [
                    {
                        **link._asdict(),
                        **{"lnurl": link.lnurl},
                    }
                    for link in await get_withdraw_links(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonable_encoder(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@withdraw_ext.get("/api/v1/links/<link_id>")
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_withdraw_link(link_id, 0)

    if not link:
        return (
            jsonable_encoder({"message": "Withdraw link does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if link.wallet != g.wallet.id:
        return jsonable_encoder({"message": "Not your withdraw link."}), HTTPStatus.FORBIDDEN

    return jsonable_encoder({**link, **{"lnurl": link.lnurl}}), HTTPStatus.OK

class CreateData(BaseModel):
    title:  str = Query(...)
    min_withdrawable:  int = Query(..., ge=1)
    max_withdrawable:  int = Query(..., ge=1)
    uses:  int = Query(..., ge=1)
    wait_time:  int = Query(..., ge=1)
    is_unique:  bool

@withdraw_ext.post("/api/v1/links")
@withdraw_ext.put("/api/v1/links/<link_id>")
@api_check_wallet_key("admin")
async def api_link_create_or_update(data: CreateData, link_id: str = None):
    if data.max_withdrawable < data.min_withdrawable:
        return (
            jsonable_encoder(
                {
                    "message": "`max_withdrawable` needs to be at least `min_withdrawable`."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    usescsv = ""
    for i in range(data.uses):
        if data.is_unique:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if link_id:
        link = await get_withdraw_link(link_id, 0)
        if not link:
            return (
                jsonify({"message": "Withdraw link does not exist."}),
                HTTPStatus.NOT_FOUND,
            )
        if link.wallet != g.wallet.id:
            return jsonify({"message": "Not your withdraw link."}), HTTPStatus.FORBIDDEN
        link = await update_withdraw_link(link_id, **data, usescsv=usescsv, used=0)
    else:
        link = await create_withdraw_link(
            wallet_id=g.wallet.id, **data, usescsv=usescsv
        )

    return (
        jsonable_encoder({**link, **{"lnurl": link.lnurl}}),
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@withdraw_ext.delete("/api/v1/links/<link_id>")
@api_check_wallet_key("admin")
async def api_link_delete(link_id):
    link = await get_withdraw_link(link_id)

    if not link:
        return (
            jsonable_encoder({"message": "Withdraw link does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if link.wallet != g.wallet.id:
        return jsonable_encoder({"message": "Not your withdraw link."}), HTTPStatus.FORBIDDEN

    await delete_withdraw_link(link_id)

    return "", HTTPStatus.NO_CONTENT


@withdraw_ext.get("/api/v1/links/<the_hash>/<lnurl_id>")
@api_check_wallet_key("invoice")
async def api_hash_retrieve(the_hash, lnurl_id):
    hashCheck = await get_hash_check(the_hash, lnurl_id)
    return jsonable_encoder(hashCheck), HTTPStatus.OK
