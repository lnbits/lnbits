from quart import jsonify, g
from http import HTTPStatus
from .crud import update_wallet_balance
from lnbits.extensions.admin import admin_ext
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.core.crud import get_admin, get_wallet


@admin_ext.route("/api/v1/admin/<wallet_id>", methods=["POST"])
@api_check_wallet_key("admin")
@api_validate_post_request(schema={"amount": {"type": "string", "required": True}})
def api_update_balance(wallet_id):
    admin = get_admin()
    if g.wallet.user != admin[0]:
        return jsonify({"message": "You're not admin."}), HTTPStatus.FORBIDDEN
    account = get_wallet(wallet_id) 
    if not account:
        return jsonify({"message": "Wallet does not exist"}), HTTPStatus.FORBIDDEN
    update_wallet_balance(wallet_id, int(g.data['amount']))
    return jsonify({"status": "Success"}), HTTPStatus.OK
