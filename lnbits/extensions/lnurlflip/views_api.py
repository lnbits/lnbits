from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnurlflip_ext
from .crud import (
    create_lnurlflip_pay,
    get_lnurlflip_pay,
    get_lnurlflip_pays,
    update_lnurlflip_pay,
    delete_lnurlflip_pay,
    create_lnurlflip_withdraw,
    get_lnurlflip_withdraw,
    get_lnurlflip_withdraws,
    update_lnurlflip_withdraw,
    delete_lnurlflip_withdraw,
    create_withdraw_hash_check,
    get_withdraw_hash_check,
)


@lnurlflip_ext.route("/api/v1/withdraws", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraws():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    try:
        return (
            jsonify(
                [
                    {
                        **withdraw._asdict(),
                        **{"lnurl": withdraw.lnurl},
                    }
                    for withdraw in await get_lnurlflip_withdraws(wallet_ids)
                ]
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_retrieve(withdraw_id):
    withdraw = await get_lnurlflip_withdraw(withdraw_id, 0)

    if not withdraw:
        return (
            jsonify({"message": "lnurlflip withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your lnurlflip withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    return jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}), HTTPStatus.OK


@lnurlflip_ext.route("/api/v1/withdraws", methods=["POST"])
@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "min_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "max_lnurlflipable": {"type": "integer", "min": 1, "required": True},
        "uses": {"type": "integer", "min": 1, "required": True},
        "wait_time": {"type": "integer", "min": 1, "required": True},
        "is_unique": {"type": "boolean", "required": True},
    }
)
async def api_withdraw_create_or_update(withdraw_id=None):
    if g.data["max_lnurlflipable"] < g.data["min_lnurlflipable"]:
        return (
            jsonify(
                {
                    "message": "`max_lnurlflipable` needs to be at least `min_lnurlflipable`."
                }
            ),
            HTTPStatus.BAD_REQUEST,
        )

    usescsv = ""
    for i in range(g.data["uses"]):
        if g.data["is_unique"]:
            usescsv += "," + str(i + 1)
        else:
            usescsv += "," + str(1)
    usescsv = usescsv[1:]

    if withdraw_id:
        withdraw = await get_lnurlflip_withdraw(withdraw_id, 0)
        if not withdraw:
            return (
                jsonify({"message": "lnurlflip withdraw does not exist."}),
                HTTPStatus.NOT_FOUND,
            )
        if withdraw.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your lnurlflip withdraw."}),
                HTTPStatus.FORBIDDEN,
            )
        withdraw = await update_lnurlflip_withdraw(
            withdraw_id, **g.data, usescsv=usescsv, used=0
        )
    else:
        withdraw = await create_lnurlflip_withdraw(
            wallet_id=g.wallet.id, **g.data, usescsv=usescsv
        )

    return (
        jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}),
        HTTPStatus.OK if withdraw_id else HTTPStatus.CREATED,
    )


@lnurlflip_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_withdraw_delete(withdraw_id):
    withdraw = await get_lnurlflip_withdraw(withdraw_id)

    if not withdraw:
        return (
            jsonify({"message": "lnurlflip withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your lnurlflip withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    await delete_lnurlflip_withdraw(withdraw_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlflip_ext.route("/api/v1/withdraws/<the_hash>/<lnurl_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_hash_retrieve(the_hash, lnurl_id):
    hashCheck = await get_withdraw_hash_check(the_hash, lnurl_id)
    return jsonify(hashCheck), HTTPStatus.OK
