from flask import g, jsonify

from lnbits.core import core_app
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status
from lnbits.settings import WALLET

from .crud import create_transaction


@core_app.route("/api/v1/invoices", methods=["POST"])
@api_validate_post_request(required_params=["amount", "memo"])
@api_check_wallet_macaroon(key_type="invoice")
def api_invoices():
    if not isinstance(g.data["amount"], int) or g.data["amount"] < 1:
        return jsonify({"message": "`amount` needs to be a positive integer."}), Status.BAD_REQUEST

    if not isinstance(g.data["memo"], str) or not g.data["memo"].strip():
        return jsonify({"message": "`memo` needs to be a valid string."}), Status.BAD_REQUEST

    try:
        r, payhash, payment_request = WALLET.create_invoice(g.data["amount"], g.data["memo"])
        server_error = not r.ok or "message" in r.json()
    except Exception:
        server_error = True

    if server_error:
        return jsonify({"message": "Unexpected backend error. Try again later."}), 500

    amount_msat = g.data["amount"] * 1000
    create_transaction(wallet_id=g.wallet.id, payhash=payhash, amount=amount_msat, memo=g.data["memo"])

    return jsonify({"payment_request": payment_request, "payment_hash": payhash}), Status.CREATED


@core_app.route("/api/v1/invoices/<payhash>", defaults={"incoming": True}, methods=["GET"])
@core_app.route("/api/v1/payments/<payhash>", defaults={"incoming": False}, methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_transaction(payhash, incoming):
    tx = g.wallet.get_transaction(payhash)

    if not tx:
        return jsonify({"message": "Transaction does not exist."}), Status.NOT_FOUND
    elif not tx.pending:
        return jsonify({"paid": True}), Status.OK

    try:
        is_settled = WALLET.get_invoice_status(payhash).settled
    except Exception:
        return jsonify({"paid": False}), Status.OK

    if is_settled is True:
        tx.set_pending(False)
        return jsonify({"paid": True}), Status.OK

    return jsonify({"paid": False}), Status.OK


@core_app.route("/api/v1/transactions", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_transactions():
    return jsonify(g.wallet.get_transactions()), Status.OK
