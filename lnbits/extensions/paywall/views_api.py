from flask import g, jsonify, request

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.helpers import Status
from lnbits.settings import WALLET

from lnbits.extensions.paywall import paywall_ext
from .crud import create_paywall, get_paywall, get_paywalls, delete_paywall


@paywall_ext.route("/api/v1/paywalls", methods=["GET"])
@api_check_wallet_key("invoice")
def api_paywalls():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([paywall._asdict() for paywall in get_paywalls(wallet_ids)]), Status.OK


@paywall_ext.route("/api/v1/paywalls", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "url": {"type": "string", "empty": False, "required": True},
        "memo": {"type": "string", "empty": False, "required": True},
        "amount": {"type": "integer", "min": 0, "required": True},
    }
)
def api_paywall_create():
    paywall = create_paywall(wallet_id=g.wallet.id, **g.data)

    return jsonify(paywall._asdict()), Status.CREATED


@paywall_ext.route("/api/v1/paywalls/<paywall_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_paywall_delete(paywall_id):
    paywall = get_paywall(paywall_id)

    if not paywall:
        return jsonify({"message": "Paywall does not exist."}), Status.NOT_FOUND

    if paywall.wallet != g.wallet.id:
        return jsonify({"message": "Not your paywall."}), Status.FORBIDDEN

    delete_paywall(paywall_id)

    return "", Status.NO_CONTENT


@paywall_ext.route("/api/v1/paywalls/<paywall_id>/invoice", methods=["GET"])
def api_paywall_get_invoice(paywall_id):
    paywall = get_paywall(paywall_id)

    try:
        checking_id, payment_request = create_invoice(
            wallet_id=paywall.wallet, amount=paywall.amount, memo=f"#paywall {paywall.memo}"
        )
    except Exception as e:
        return jsonify({"message": str(e)}), Status.INTERNAL_SERVER_ERROR

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), Status.OK


@paywall_ext.route("/api/v1/paywalls/<paywall_id>/check_invoice", methods=["POST"])
@api_validate_post_request(schema={"checking_id": {"type": "string", "empty": False, "required": True}})
def api_paywal_check_invoice(paywall_id):
    paywall = get_paywall(paywall_id)

    if not paywall:
        return jsonify({"message": "Paywall does not exist."}), Status.NOT_FOUND

    try:
        is_paid = not WALLET.get_invoice_status(g.data["checking_id"]).pending
    except Exception:
        return jsonify({"paid": False}), Status.OK

    if is_paid:
        wallet = get_wallet(paywall.wallet)
        payment = wallet.get_payment(g.data["checking_id"])
        payment.set_pending(False)

        return jsonify({"paid": True, "url": paywall.url}), Status.OK

    return jsonify({"paid": False}), Status.OK
