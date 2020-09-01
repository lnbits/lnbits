from flask import g, jsonify, request
from http import HTTPStatus
from binascii import unhexlify

from lnbits.core import core_app
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import WALLET

from ..services import create_invoice, pay_invoice


@core_app.route("/api/v1/payments", methods=["GET"])
@api_check_wallet_key("invoice")
def api_payments():
    if "check_pending" in request.args:
        g.wallet.delete_expired_payments()

        for payment in g.wallet.get_payments(complete=False, pending=True):
            if payment.is_out:
                payment.set_pending(WALLET.get_payment_status(payment.checking_id).pending)
            else:
                payment.set_pending(WALLET.get_invoice_status(payment.checking_id).pending)

    return jsonify(g.wallet.get_payments()), HTTPStatus.OK


@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "amount": {"type": "integer", "min": 1, "required": True},
        "memo": {"type": "string", "empty": False, "required": True, "excludes": "description_hash"},
        "description_hash": {"type": "string", "empty": False, "required": True, "excludes": "memo"},
    }
)
def api_payments_create_invoice():
    if "description_hash" in g.data:
        description_hash = unhexlify(g.data["description_hash"])
        memo = ""
    else:
        description_hash = b""
        memo = g.data["memo"]

    try:
        checking_id, payment_request = create_invoice(
            wallet_id=g.wallet.id, amount=g.data["amount"], memo=memo, description_hash=description_hash
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), HTTPStatus.CREATED


@api_check_wallet_key("admin")
@api_validate_post_request(schema={"bolt11": {"type": "string", "empty": False, "required": True}})
def api_payments_pay_invoice():
    try:
        checking_id = pay_invoice(wallet_id=g.wallet.id, bolt11=g.data["bolt11"])
    except ValueError as e:
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except PermissionError as e:
        return jsonify({"message": str(e)}), HTTPStatus.FORBIDDEN
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"checking_id": checking_id}), HTTPStatus.CREATED


@core_app.route("/api/v1/payments", methods=["POST"])
@api_validate_post_request(schema={"out": {"type": "boolean", "required": True}})
def api_payments_create():
    if g.data["out"] is True:
        return api_payments_pay_invoice()
    return api_payments_create_invoice()


@core_app.route("/api/v1/payments/<checking_id>", methods=["GET"])
@api_check_wallet_key("invoice")
def api_payment(checking_id):
    payment = g.wallet.get_payment(checking_id)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return jsonify({"paid": True}), HTTPStatus.OK

    try:
        if payment.is_out:
            is_paid = not WALLET.get_payment_status(checking_id).pending
        elif payment.is_in:
            is_paid = not WALLET.get_invoice_status(checking_id).pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        payment.set_pending(False)
        return jsonify({"paid": True}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK
