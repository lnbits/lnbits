from flask import g, jsonify, request

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status

from lnbits.extensions.amilk import amilk_ext
from .crud import create_amilk, get_amilk, get_amilks, delete_amilk


@amilk_ext.route("/api/v1/amilk", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_amilks():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([amilk._asdict() for amilk in get_amilks(wallet_ids)]), Status.OK


@amilk_ext.route("/api/v1/amilk", methods=["POST"])
@api_check_wallet_macaroon(key_type="invoice")
@api_validate_post_request(schema={
    "url": {"type": "string", "empty": False, "required": True},
    "memo": {"type": "string", "empty": False, "required": True},
    "amount": {"type": "integer", "min": 0, "required": True},
})
def api_amilk_create():
    amilk = create_amilk(wallet_id=g.wallet.id, **g.data)

    return jsonify(amilk._asdict()), Status.CREATED


@amilk_ext.route("/api/v1/amilk/<amilk_id>", methods=["DELETE"])
@api_check_wallet_macaroon(key_type="invoice")
def api_amilk_delete(amilk_id):
    amilk = get_amilk(amilk_id)

    if not amilk:
        return jsonify({"message": "Paywall does not exist."}), Status.NOT_FOUND

    if amilk.wallet != g.wallet.id:
        return jsonify({"message": "Not your amilk."}), Status.FORBIDDEN

    delete_amilk(amilk_id)

    return "", Status.NO_CONTENT
