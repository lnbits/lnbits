import hashlib
from quart import g, jsonify, url_for, websocket
from http import HTTPStatus
import httpx

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import lnurlpos_ext

from lnbits.extensions.lnurlpos import lnurlpos_ext
from .crud import (
    create_lnurlpos,
    update_lnurlpos,
    get_lnurlpos,
    get_lnurlposs,
    delete_lnurlpos,
)
from lnbits.utils.exchange_rates import currencies


@lnurlpos_ext.route("/api/v1/currencies", methods=["GET"])
async def api_list_currencies_available():
    return jsonify(list(currencies.keys()))


#######################lnurlpos##########################


@lnurlpos_ext.route("/api/v1/lnurlpos", methods=["POST"])
@lnurlpos_ext.route("/api/v1/lnurlpos/<lnurlpos_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "wallet": {"type": "string", "empty": False, "required": True},
        "currency": {"type": "string", "empty": False, "required": False},
    }
)
async def api_lnurlpos_create_or_update(lnurlpos_id=None):
    if not lnurlpos_id:
        lnurlpos = await create_lnurlpos(**g.data)
        return jsonify(lnurlpos._asdict()), HTTPStatus.CREATED
    else:
        lnurlpos = await update_lnurlpos(lnurlpos_id=lnurlpos_id, **g.data)
        return jsonify(lnurlpos._asdict()), HTTPStatus.OK


@lnurlpos_ext.route("/api/v1/lnurlpos", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_lnurlposs_retrieve():
    wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    try:
        return (
            jsonify(
                [{**lnurlpos._asdict()} for lnurlpos in await get_lnurlposs(wallet_ids)]
            ),
            HTTPStatus.OK,
        )
    except:
        return ""


@lnurlpos_ext.route("/api/v1/lnurlpos/<lnurlpos_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_lnurlpos_retrieve(lnurlpos_id):
    lnurlpos = await get_lnurlpos(lnurlpos_id)
    if not lnurlpos:
        return jsonify({"message": "lnurlpos does not exist"}), HTTPStatus.NOT_FOUND
    if not lnurlpos.lnurl_toggle:
        return (
            jsonify({**lnurlpos._asdict()}),
            HTTPStatus.OK,
        )
    return (
        jsonify({**lnurlpos._asdict(), **{"lnurl": lnurlpos.lnurl}}),
        HTTPStatus.OK,
    )


@lnurlpos_ext.route("/api/v1/lnurlpos/<lnurlpos_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_lnurlpos_delete(lnurlpos_id):
    lnurlpos = await get_lnurlpos(lnurlpos_id)

    if not lnurlpos:
        return jsonify({"message": "Wallet link does not exist."}), HTTPStatus.NOT_FOUND

    await delete_lnurlpos(lnurlpos_id)

    return "", HTTPStatus.NO_CONTENT
