from flask import g, jsonify, request

from lnbits import bolt11
from lnbits.core import core_app
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status
from lnbits.settings import FEE_RESERVE, WALLET

from ..crud import create_payment


@core_app.route("/api/v1/payments", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_payments():
    if "check_pending" in request.args:
        for payment in g.wallet.get_payments(include_all_pending=True):
            if payment.is_out:
                payment.set_pending(WALLET.get_payment_status(payment.payhash).pending)
            elif payment.is_in:
                payment.set_pending(WALLET.get_invoice_status(payment.payhash).pending)

    return jsonify(g.wallet.get_payments()), Status.OK


@api_check_wallet_macaroon(key_type="invoice")
@api_validate_post_request(required_params=["amount", "memo"])
def api_payments_create_invoice():
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
        return jsonify({"message": "Unexpected backend error. Try again later."}), Status.INTERNAL_SERVER_ERROR

    amount_msat = g.data["amount"] * 1000
    create_payment(wallet_id=g.wallet.id, payhash=payhash, amount=amount_msat, memo=g.data["memo"])

    return jsonify({"payment_request": payment_request, "payment_hash": payhash}), Status.CREATED


@api_check_wallet_macaroon(key_type="invoice")
@api_validate_post_request(required_params=["bolt11"])
def api_payments_pay_invoice():
    if not isinstance(g.data["bolt11"], str) or not g.data["bolt11"].strip():
        return jsonify({"message": "`bolt11` needs to be a valid string."}), Status.BAD_REQUEST

    try:
        invoice = bolt11.decode(g.data["bolt11"])

        if invoice.amount_msat == 0:
            return jsonify({"message": "Amountless invoices not supported."}), Status.BAD_REQUEST

        if invoice.amount_msat > g.wallet.balance_msat:
            return jsonify({"message": "Insufficient balance."}), Status.FORBIDDEN

        create_payment(
            wallet_id=g.wallet.id,
            payhash=invoice.payment_hash,
            amount=-invoice.amount_msat,
            memo=invoice.description,
            fee=-invoice.amount_msat * FEE_RESERVE,
        )

        r, server_error, fee_msat, error_message = WALLET.pay_invoice(g.data["bolt11"])

    except Exception as e:
        server_error = True
        error_message = str(e)

    if server_error:
        return jsonify({"message": error_message}), Status.INTERNAL_SERVER_ERROR

    return jsonify({"payment_hash": invoice.payment_hash}), Status.CREATED


@core_app.route("/api/v1/payments", methods=["POST"])
@api_validate_post_request(required_params=["out"])
def api_payments_create():
    if g.data["out"] is True:
        return api_payments_pay_invoice()
    return api_payments_create_invoice()


@core_app.route("/api/v1/payments/<payhash>", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_payment(payhash):
    payment = g.wallet.get_payment(payhash)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), Status.NOT_FOUND
    elif not payment.pending:
        return jsonify({"paid": True}), Status.OK

    try:
        if payment.is_out:
            is_paid = WALLET.get_payment_status(payhash).paid
        elif payment.is_in:
            is_paid = WALLET.get_invoice_status(payhash).paid
    except Exception:
        return jsonify({"paid": False}), Status.OK

    if is_paid is True:
        payment.set_pending(False)
        return jsonify({"paid": True}), Status.OK

    return jsonify({"paid": False}), Status.OK
