from quart import jsonify, g, request
from http import HTTPStatus
from .crud import update_wallet_balance
from lnbits.extensions.admin import admin_ext
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.core.crud import get_wallet
from .crud import get_admin,update_admin
import json

@admin_ext.route("/api/v1/admin/<wallet_id>/<topup_amount>", methods=["GET"])
@api_check_wallet_key("admin")
async def api_update_balance(wallet_id, topup_amount):
    print(g.data.wallet)
    try:
        wallet = await get_wallet(wallet_id)
    except:
        return (
            jsonify({"error": "Not allowed: not an admin"}),
            HTTPStatus.FORBIDDEN,
        )
    print(wallet)
    print(topup_amount)
    return jsonify({"status": "Success"}), HTTPStatus.OK


@admin_ext.route("/api/v1/admin/", methods=["POST"])
@api_check_wallet_key("admin")
@api_validate_post_request(schema={})
async def api_update_admin():
    body = await request.get_json()
    admin = await get_admin()
    print(g.wallet[2])
    print(body["admin_user"])
    if not admin.admin_user == g.wallet[2] and admin.admin_user != None:
        return (
            jsonify({"error": "Not allowed: not an admin"}),
            HTTPStatus.FORBIDDEN,
        )
    updated = await update_admin(body)
    print(updated)
    return jsonify({"status": "Success"}), HTTPStatus.OK