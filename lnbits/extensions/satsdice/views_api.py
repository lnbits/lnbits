from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import satsdice_ext
from .crud import (
    create_satsdice_pay,
    get_satsdice_pay,
    get_satsdice_pays,
    update_satsdice_pay,
    delete_satsdice_pay,
    create_satsdice_withdraw,
    get_satsdice_withdraw,
    get_satsdice_withdraws,
    update_satsdice_withdraw,
    delete_satsdice_withdraw,
    create_withdraw_hash_check,
)

################LNURL pay


@satsdice_ext.route("/api/v1/links", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_links():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    try:
        return (
            jsonify(
                [
                    {**link._asdict(), **{"lnurl": link.lnurl}}
                    for link in await get_satsdice_pays(wallet_ids)
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


@satsdice_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_satsdice_pay(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK


@satsdice_ext.route("/api/v1/links", methods=["POST"])
@satsdice_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "base_url": {"type": "string", "empty": False, "required": True},
        "min_bet": {"type": "number", "required": True},
        "max_bet": {"type": "number", "required": True},
        "multiplier": {"type": "number", "required": True},
        "chance": {"type": "float", "required": True},
        "haircut": {"type": "number", "required": True},
    }
)
async def api_link_create_or_update(link_id=None):
    if g.data["min_bet"] > g.data["max_bet"]:
        return jsonify({"message": "Min is greater than max."}), HTTPStatus.BAD_REQUEST
    if link_id:
        link = await get_satsdice_pay(link_id)

        if not link:
            return (
                jsonify({"message": "Satsdice does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if link.wallet != g.wallet.id:
            return (
                jsonify({"message": "Come on, seriously, this isn't your satsdice!"}),
                HTTPStatus.FORBIDDEN,
            )

        link = await update_satsdice_pay(link_id, **g.data)
    else:
        link = await create_satsdice_pay(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify({**link._asdict(), **{"lnurl": link.lnurl}}),
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@satsdice_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_link_delete(link_id):
    link = await get_satsdice_pay(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    await delete_satsdice_pay(link_id)

    return "", HTTPStatus.NO_CONTENT


##########LNURL withdraw


@satsdice_ext.route("/api/v1/withdraws", methods=["GET"])
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
                    for withdraw in await get_satsdice_withdraws(wallet_ids)
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


@satsdice_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_retrieve(withdraw_id):
    withdraw = await get_satsdice_withdraw(withdraw_id, 0)

    if not withdraw:
        return (
            jsonify({"message": "satsdice withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your satsdice withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    return jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}), HTTPStatus.OK


@satsdice_ext.route("/api/v1/withdraws", methods=["POST"])
@satsdice_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "min_satsdiceable": {"type": "integer", "min": 1, "required": True},
        "max_satsdiceable": {"type": "integer", "min": 1, "required": True},
        "uses": {"type": "integer", "min": 1, "required": True},
        "wait_time": {"type": "integer", "min": 1, "required": True},
        "is_unique": {"type": "boolean", "required": True},
    }
)
async def api_withdraw_create_or_update(withdraw_id=None):
    if g.data["max_satsdiceable"] < g.data["min_satsdiceable"]:
        return (
            jsonify(
                {
                    "message": "`max_satsdiceable` needs to be at least `min_satsdiceable`."
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
        withdraw = await get_satsdice_withdraw(withdraw_id, 0)
        if not withdraw:
            return (
                jsonify({"message": "satsdice withdraw does not exist."}),
                HTTPStatus.NOT_FOUND,
            )
        if withdraw.wallet != g.wallet.id:
            return (
                jsonify({"message": "Not your satsdice withdraw."}),
                HTTPStatus.FORBIDDEN,
            )
        withdraw = await update_satsdice_withdraw(
            withdraw_id, **g.data, usescsv=usescsv, used=0
        )
    else:
        withdraw = await create_satsdice_withdraw(
            wallet_id=g.wallet.id, **g.data, usescsv=usescsv
        )

    return (
        jsonify({**withdraw._asdict(), **{"lnurl": withdraw.lnurl}}),
        HTTPStatus.OK if withdraw_id else HTTPStatus.CREATED,
    )


@satsdice_ext.route("/api/v1/withdraws/<withdraw_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_withdraw_delete(withdraw_id):
    withdraw = await get_satsdice_withdraw(withdraw_id)

    if not withdraw:
        return (
            jsonify({"message": "satsdice withdraw does not exist."}),
            HTTPStatus.NOT_FOUND,
        )

    if withdraw.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not your satsdice withdraw."}),
            HTTPStatus.FORBIDDEN,
        )

    await delete_satsdice_withdraw(withdraw_id)

    return "", HTTPStatus.NO_CONTENT


@satsdice_ext.route("/api/v1/withdraws/<the_hash>/<lnurl_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_withdraw_hash_retrieve(the_hash, lnurl_id):
    hashCheck = await get_withdraw_hash_check(the_hash, lnurl_id)
    return jsonify(hashCheck), HTTPStatus.OK
