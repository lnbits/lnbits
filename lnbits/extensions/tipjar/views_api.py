from quart import g, jsonify
from http import HTTPStatus

from lnbits.decorators import api_validate_post_request, api_check_wallet_key
from lnbits.core.crud import get_user

from . import tipjar_ext
from .helpers import get_charge_details
from .crud import (
    create_tipjar,
    get_tipjar,
    create_tip,
    get_tipjars,
    get_tip,
    get_tips,
    update_tip,
    update_tipjar,
    delete_tip,
    delete_tipjar,
)
from ..satspay.crud import create_charge


@tipjar_ext.route("/api/v1/tipjars", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "required": True},
        "wallet": {"type": "string", "required": True},
        "webhook": {"type": "string"},
        "onchain": {"type": "string"},
    }
)
async def api_create_tipjar():
    """Create a tipjar, which holds data about how/where to post tips"""
    try:
        tipjar = await create_tipjar(**g.data)
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify(tipjar._asdict()), HTTPStatus.CREATED


@tipjar_ext.route("/api/v1/tips", methods=["POST"])
@api_validate_post_request(
    schema={
        "name": {"type": "string"},
        "sats": {"type": "integer", "required": True},
        "tipjar": {"type": "integer", "required": True},
        "message": {"type": "string"},
    }
)
async def api_create_tip():
    """Take data from tip form and return satspay charge"""
    sats = g.data["sats"]
    message = g.data.get("message", "")[:144]
    if not message:
        message = "No message"
    tipjar_id = g.data["tipjar"]
    tipjar = await get_tipjar(tipjar_id)
    webhook = tipjar.webhook
    charge_details = await get_charge_details(tipjar.id)
    name = g.data.get("name", "")[:25]
    # Ensure that description string can be split reliably
    name = name.replace('"', "''")
    if not name:
        name = "Anonymous"
    description = f'"{name}": {message}'
    charge = await create_charge(
        amount=sats,
        webhook=webhook,
        description=description,
        **charge_details,
    )
    await create_tip(
        id=charge.id,
        wallet=tipjar.wallet,
        message=message,
        name=name,
        sats=g.data["sats"],
        tipjar=g.data["tipjar"],
    )
    return (jsonify({"redirect_url": f"/satspay/{charge.id}"}), HTTPStatus.OK)


@tipjar_ext.route("/api/v1/tipjars", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_tipjars():
    """Return list of all tipjars assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    tipjars = []
    for wallet_id in wallet_ids:
        new_tipjars = await get_tipjars(wallet_id)
        tipjars += new_tipjars if new_tipjars else []
    return (
        jsonify([tipjar._asdict() for tipjar in tipjars] if tipjars else []),
        HTTPStatus.OK,
    )


@tipjar_ext.route("/api/v1/tips", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_tips():
    """Return list of all tips assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(g.wallet.user)).wallet_ids
    tips = []
    for wallet_id in wallet_ids:
        new_tips = await get_tips(wallet_id)
        tips += new_tips if new_tips else []
    return (
        jsonify([tip._asdict() for tip in tips] if tips else []),
        HTTPStatus.OK,
    )


@tipjar_ext.route("/api/v1/tips/<tip_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
async def api_update_tip(tip_id=None):
    """Update a tip with the data given in the request"""
    if tip_id:
        tip = await get_tip(tip_id)

        if not tip:
            return (
                jsonify({"message": "Tip does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if tip.wallet != g.wallet.id:
            return (jsonify({"message": "Not your tip."}), HTTPStatus.FORBIDDEN)

        tip = await update_tip(tip_id, **g.data)
    else:
        return (
            jsonify({"message": "No tip ID specified"}),
            HTTPStatus.BAD_REQUEST,
        )
    return jsonify(tip._asdict()), HTTPStatus.CREATED


@tipjar_ext.route("/api/v1/tipjars/<tipjar_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
async def api_update_tipjar(tipjar_id=None):
    """Update a tipjar with the data given in the request"""
    if tipjar_id:
        tipjar = await get_tipjar(tipjar_id)

        if not tipjar:
            return (
                jsonify({"message": "TipJar does not exist."}),
                HTTPStatus.NOT_FOUND,
            )

        if tipjar.wallet != g.wallet.id:
            return (jsonify({"message": "Not your tipjar."}), HTTPStatus.FORBIDDEN)

        tipjar = await update_tipjar(tipjar_id, **g.data)
    else:
        return (jsonify({"message": "No tipjar ID specified"}), HTTPStatus.BAD_REQUEST)
    return jsonify(tipjar._asdict()), HTTPStatus.CREATED


@tipjar_ext.route("/api/v1/tips/<tip_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_delete_tip(tip_id):
    """Delete the tip with the given tip_id"""
    tip = await get_tip(tip_id)
    if not tip:
        return (jsonify({"message": "No tip with this ID!"}), HTTPStatus.NOT_FOUND)
    if tip.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not authorized to delete this tip!"}),
            HTTPStatus.FORBIDDEN,
        )
    await delete_tip(tip_id)

    return "", HTTPStatus.NO_CONTENT


@tipjar_ext.route("/api/v1/tipjars/<tipjar_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_delete_tipjar(tipjar_id):
    """Delete the tipjar with the given tipjar_id"""
    tipjar = await get_tipjar(tipjar_id)
    if not tipjar:
        return (jsonify({"message": "No tipjar with this ID!"}), HTTPStatus.NOT_FOUND)
    if tipjar.wallet != g.wallet.id:
        return (
            jsonify({"message": "Not authorized to delete this tipjar!"}),
            HTTPStatus.FORBIDDEN,
        )
    await delete_tipjar(tipjar_id)

    return "", HTTPStatus.NO_CONTENT
