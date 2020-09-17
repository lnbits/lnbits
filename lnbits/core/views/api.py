from flask import g, jsonify, request
from http import HTTPStatus
from binascii import unhexlify

from lnbits import bolt11
from lnbits.core import core_app
from lnbits.core.services import create_invoice, pay_invoice, update_wallet_balance
from lnbits.core.crud import delete_expired_invoices, get_admin, get_account
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import WALLET, LNBITS_ADMIN_USERS


@core_app.route("/api/v1/payments", methods=["GET"])
@api_check_wallet_key("invoice")
def api_payments():
    if "check_pending" in request.args:
        delete_expired_invoices()

        for payment in g.wallet.get_payments(complete=False, pending=True, exclude_uncheckable=True):
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
        payment_hash, payment_request = create_invoice(
            wallet_id=g.wallet.id, amount=g.data["amount"], memo=memo, description_hash=description_hash
        )
    except Exception as e:
        g.db.rollback()
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    invoice = bolt11.decode(payment_request)
    return (
        jsonify(
            {
                "payment_hash": invoice.payment_hash,
                "payment_request": payment_request,
                # maintain backwards compatibility with API clients:
                "checking_id": invoice.payment_hash,
            }
        ),
        HTTPStatus.CREATED,
    )


@api_check_wallet_key("admin")
@api_validate_post_request(schema={"bolt11": {"type": "string", "empty": False, "required": True}})
def api_payments_pay_invoice():
    try:
        payment_hash = pay_invoice(wallet_id=g.wallet.id, payment_request=g.data["bolt11"])
    except ValueError as e:
        return jsonify({"message": str(e)}), HTTPStatus.BAD_REQUEST
    except PermissionError as e:
        return jsonify({"message": str(e)}), HTTPStatus.FORBIDDEN
    except Exception as e:
        print(e)
        g.db.rollback()
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return (
        jsonify(
            {
                "payment_hash": payment_hash,
                # maintain backwards compatibility with API clients:
                "checking_id": payment_hash,
            }
        ),
        HTTPStatus.CREATED,
    )


@core_app.route("/api/v1/payments", methods=["POST"])
@api_validate_post_request(schema={"out": {"type": "boolean", "required": True}})
def api_payments_create():
    if g.data["out"] is True:
        return api_payments_pay_invoice()
    return api_payments_create_invoice()


@core_app.route("/api/v1/payments/<payment_hash>", methods=["GET"])
@api_check_wallet_key("invoice")
def api_payment(payment_hash):
    payment = g.wallet.get_payment(payment_hash)

    if not payment:
        return jsonify({"message": "Payment does not exist."}), HTTPStatus.NOT_FOUND
    elif not payment.pending:
        return jsonify({"paid": True}), HTTPStatus.OK

    try:
        if payment.is_uncheckable:
            pass
        elif payment.is_out:
            is_paid = not WALLET.get_payment_status(payment.checking_id).pending
        elif payment.is_in:
            is_paid = not WALLET.get_invoice_status(payment.checking_id).pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        payment.set_pending(False)
        return jsonify({"paid": True}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK


@core_app.route("/api/v1/balance", methods=["POST"])
@api_check_wallet_key("admin")
@api_validate_post_request(schema={"amount": {"type": "integer", "min": 1, "required": True}})
def api_update_balance():
    if g.wallet.user in LNBITS_ADMIN_USERS:
        return update_wallet_balance(g.wallet.id, g.data["amount"])
    return jsonify({"message": "Not an admin wallet"}), HTTPStatus.INTERNAL_SERVER_ERROR


@core_app.route("/api/v1/admin", methods=["POST"])
@api_validate_post_request(
        schema={
        
        "user": {"type": "string", "empty": False, "required": True},
        "site_title": {"type": "string", "empty": False, "required": True},
        "tagline": {"type": "string", "empty": False, "required": True},
        "primary_color": {"type": "string", "empty": False, "required": True},
        "secondary_color": {"type": "string", "empty": False, "required": True},
        "allowed_users": {"type": "string"},
        "default_wallet_name": {"type": "string", "empty": False, "required": True},
        "data_folder": {"type": "string", "empty": False, "required": True},
        "disabled_ext": {"type": "string", "empty": False, "required": True},
        "service_fee": {"type": "integer", "min": 0, "max": 90, "required": True},
    })
def api_admin():

    admin = get_admin(None)

    if admin.user != None and admin.user != g.data["user"]:
        return jsonify({"message": "Admin exists and it isnt you!"}), HTTPStatus.FORBIDDEN
    if admin.user == None:
        account = get_account(g.data["user"])
        if not account:
            return jsonify({"message": "Admin doesnt exist and neither do you!"}), HTTPStatus.FORBIDDEN
    admin = get_admin(**g.data)
    return jsonify(admin)