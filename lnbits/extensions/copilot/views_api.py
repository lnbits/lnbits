import hashlib
from quart import g, jsonify, url_for, websocket
from http import HTTPStatus
import httpx

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import copilot_ext

from lnbits.extensions.copilot import copilot_ext
from .crud import (
    create_copilot,
    update_copilot,
    get_copilot,
    get_copilots,
    delete_copilot,
)

#############################COPILOT##########################


@copilot_ext.route("/api/v1/copilot", methods=["POST"])
@copilot_ext.route("/api/v1/copilot/<copilot_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "lnurl_toggle": {"type": "integer", "empty": False, "required": True},
        "wallet": {"type": "string", "empty": False, "required": False},
        "animation1": {"type": "string", "required": False},
        "animation2": {"type": "string", "required": False},
        "animation3": {"type": "string", "required": False},
        "animation1threshold": {"type": "string", "required": False},
        "animation2threshold": {"type": "string", "required": False},
        "animation3threshold": {"type": "string", "required": False},
        "animation1webhook": {"type": "string", "required": False},
        "animation2webhook": {"type": "string", "required": False},
        "animation3webhook": {"type": "string", "required": False},
        "lnurl_title": {"type": "string", "empty": False, "required": False},
        "show_message": {"type": "integer", "empty": False, "required": False},
        "show_ack": {"type": "integer", "empty": False, "required": True},
        "show_price": {"type": "integer", "empty": False, "required": True},
    }
)
async def api_copilot_create_or_update(copilot_id=None):
    if not copilot_id:
        copilot = await create_copilot(user=g.wallet.user, **g.data)
        return jsonify(copilot._asdict()), HTTPStatus.CREATED
    else:
        copilot = await update_copilot(copilot_id=copilot_id, **g.data)
        return jsonify(copilot._asdict()), HTTPStatus.OK


@copilot_ext.route("/api/v1/copilot", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_copilots_retrieve():
    try:
        return (
            jsonify(
                [{**copilot._asdict()} for copilot in await get_copilots(g.wallet.user)]
            ),
            HTTPStatus.OK,
        )
    except:
        return ""


@copilot_ext.route("/api/v1/copilot/<copilot_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_copilot_retrieve(copilot_id):
    copilot = await get_copilot(copilot_id)

    if not copilot:
        return jsonify({"message": "copilot does not exist"}), HTTPStatus.NOT_FOUND

    return (
        jsonify({copilot._asdict()}),
        HTTPStatus.OK,
    )


@copilot_ext.route("/api/v1/copilot/<copilot_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_copilot_delete(copilot_id):
    copilot = await get_copilot(copilot_id)

    if not copilot:
        return jsonify({"message": "Wallet link does not exist."}), HTTPStatus.NOT_FOUND

    await delete_copilot(copilot_id)

    return "", HTTPStatus.NO_CONTENT