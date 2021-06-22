# import json
# import httpx
# (use httpx just like requests, except instead of response.ok there's only the
#  response.is_error that is its inverse)

from quart import g, redirect, request  # jsonify
from http import HTTPStatus

from lnbits.decorators import api_validate_post_request, api_check_wallet_key

from . import TwitchAlerts_ext
from .crud import get_charge_details
from ..satspay.crud import create_charge, get_charge, delete_charge


@TwitchAlerts_ext.route("/api/v1/createdonation", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string"},
        "sats": {"type": "integer", "required": True},
        "service": {"type": "string", "required": True},
        "cur_code": {"type": "string", "required": True},
        "amount": {"type": "float", "required": True}
    }
)
async def api_create_donation():
    """Takes data from donation form and creates+returns SatsPay charge"""
    webhook_base = request.scheme + "://" + request.headers["Host"]
    charge_details = await get_charge_details(g.data["service"])
    charge = await create_charge(
        webhook=webhook_base + "/TwitchAlerts/api/v1/postdonation",
        **charge_details)
    return redirect(f"/satspay/{charge.id}")


@TwitchAlerts_ext.route("/api/v1/postdonation", methods=["POST"])
# @api_validate_post_request(
#     schema={
#         "id": {"type": "string", "required": True},
#         "description": {"type": "string", "allow_unknown": True},
#         "onchainaddress": {"type": "string", "allow_unknown": True},
#         "payment_request": {"type": "string", "allow_unknown": True},
#         "payment_hash": {"type": "string", "allow_unknown": True},
#         "time": {"type": "integer", "allow_unknown": True},
#         "amount": {"type": "integer", "allow_unknown": True},
#         "paid": {"type": "boolean", "allow_unknown": True},
#         "timestamp": {"type": "integer", "allow_unknown": True},
#         "completelink": {"type": "string", "allow_unknown": True},
#     }
# )
async def api_post_donation():
    """Posts a paid donation to Stremalabs/StreamElements.

    This endpoint acts as a webhook for the SatsPayServer extension."""
    data = await request.get_json(force=True)
    charge_id = data["id"]
    charge = await get_charge(charge_id)
    print(charge)
    if charge and charge.paid:
        await delete_charge(charge_id)
        print("This endpoint works!")
        return "", HTTPStatus.OK
    else:
        return "", HTTPStatus.OK
