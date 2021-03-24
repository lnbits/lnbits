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


@lnurlp_ext.route("/api/v1/currencies", methods=["GET"])
async def api_list_currencies_available():
    return jsonify(list(currencies.keys()))


@lnurlp_ext.route("/api/v1/links", methods=["GET"])
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
                    for link in await get_pay_links(wallet_ids)
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


@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_link_retrieve(link_id):
    link = await get_pay_link(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    return jsonify({**link._asdict(), **{"lnurl": link.lnurl}}), HTTPStatus.OK


@lnurlp_ext.route("/api/v1/links", methods=["POST"])
@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "description": {"type": "string", "empty": False, "required": True},
        "min": {"type": "number", "min": 0.01, "required": True},
        "max": {"type": "number", "min": 0.01, "required": True},
        "currency": {"type": "string", "nullable": True, "required": False},
        "comment_chars": {"type": "integer", "required": True, "min": 0, "max": 800},
        "webhook_url": {"type": "string", "required": False},
        "success_text": {"type": "string", "required": False},
        "success_url": {"type": "string", "required": False},
    }
)
async def api_link_create_or_update(link_id=None):
    if g.data["min"] > g.data["max"]:
        return jsonify({"message": "Min is greater than max."}), HTTPStatus.BAD_REQUEST

    if g.data.get("currency") == None and (
        round(g.data["min"]) != g.data["min"] or round(g.data["max"]) != g.data["max"]
    ):
        return jsonify({"message": "Must use full satoshis."}), HTTPStatus.BAD_REQUEST

    if link_id:
        link = await get_pay_link(link_id)

        if not link:
            return (
                jsonify({"message": "Pay link does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if link.wallet != g.wallet.id:
            return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

        link = await update_pay_link(link_id, **g.data)
    else:
        link = await create_pay_link(wallet_id=g.wallet.id, **g.data)

    return (
        jsonify({**link._asdict(), **{"lnurl": link.lnurl}}),
        HTTPStatus.OK if link_id else HTTPStatus.CREATED,
    )


@lnurlp_ext.route("/api/v1/links/<link_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_link_delete(link_id):
    link = await get_pay_link(link_id)

    if not link:
        return jsonify({"message": "Pay link does not exist."}), HTTPStatus.NOT_FOUND

    if link.wallet != g.wallet.id:
        return jsonify({"message": "Not your pay link."}), HTTPStatus.FORBIDDEN

    await delete_pay_link(link_id)

    return "", HTTPStatus.NO_CONTENT


@lnurlp_ext.route("/api/v1/rate/<currency>", methods=["GET"])
async def api_check_fiat_rate(currency):
    try:
        rate = await get_fiat_rate_satoshis(currency)
    except AssertionError:
        rate = None

    return jsonify({"rate": rate}), HTTPStatus.OK
