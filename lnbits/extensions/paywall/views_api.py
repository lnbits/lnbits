from flask import g, jsonify, request

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status

from lnbits.extensions.paywall import paywall_ext
from .crud import create_paywall, get_paywall, get_paywalls, delete_paywall


@paywall_ext.route("/api/v1/paywalls", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_paywalls():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([paywall._asdict() for paywall in get_paywalls(wallet_ids)]), Status.OK


@paywall_ext.route("/api/v1/paywalls", methods=["POST"])
@api_check_wallet_macaroon(key_type="invoice")
@api_validate_post_request(schema={
    "url": {"type": "string", "empty": False, "required": True},
    "memo": {"type": "string", "empty": False, "required": True},
    "amount": {"type": "integer", "min": 0, "required": True},
})
def api_paywall_create():
    paywall = create_paywall(wallet_id=g.wallet.id, **g.data)

    return jsonify(paywall._asdict()), Status.CREATED


@paywall_ext.route("/api/v1/paywalls/<paywall_id>", methods=["DELETE"])
@api_check_wallet_macaroon(key_type="invoice")
def api_paywall_delete(paywall_id):
    paywall = get_paywall(paywall_id)

    if not paywall:
        return jsonify({"message": "Paywall does not exist."}), Status.NOT_FOUND

    if paywall.wallet != g.wallet.id:
        return jsonify({"message": "Not your paywall."}), Status.FORBIDDEN

    delete_paywall(paywall_id)

    return "", Status.NO_CONTENT
