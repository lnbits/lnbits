import hashlib
from quart import g, jsonify, url_for, websocket
from http import HTTPStatus
import httpx

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from .views import updater

from . import lnurlpos_ext

from lnbits.extensions.lnurlpos import lnurlpos_ext
from .crud import (
    create_lnurlpos,
    update_lnurlpos,
    get_lnurlpos,
    get_lnurlposs,
    delete_lnurlpos,
)

#######################lnurlpos##########################


@lnurlpos_ext.route("/api/v1/lnurlpos", methods=["POST"])
@lnurlpos_ext.route("/api/v1/lnurlpos/<lnurlpos_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
            title: str,
    wallet: Optional[str] = None,
    message: Optional[str] = 0,
    currency: Optional[str] = None,
        "title": {"type": "string", "empty": False, "required": True},
        "wallet": {"type": "string", "empty": False, "required": True},
        "message": {"type": "string", "empty": False, "required": True},
        "currency": {"type": "string", "empty": False, "required": False}
    }
)
async def api_lnurlpos_create_or_update(lnurlpos_id=None):
    if not lnurlpos_id:
        lnurlpos = await create_lnurlpos(user=g.wallet.user, **g.data)
        return jsonify(lnurlpos._asdict()), HTTPStatus.CREATED
    else:
        lnurlpos = await update_lnurlpos(lnurlpos_id=lnurlpos_id, **g.data)
        return jsonify(lnurlpos._asdict()), HTTPStatus.OK


@lnurlpos_ext.route("/api/v1/lnurlpos", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_lnurlposs_retrieve():
    try:
        return (
            jsonify(
                [{**lnurlpos._asdict()} for lnurlpos in await get_lnurlposs(g.wallet.user)]
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
