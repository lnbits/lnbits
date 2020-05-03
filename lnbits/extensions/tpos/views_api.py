from flask import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.settings import WALLET

from lnbits.extensions.tpos import tpos_ext
from .crud import create_tpos, get_tpos, get_tposs, delete_tpos


@tpos_ext.route("/api/v1/tposs", methods=["GET"])
@api_check_wallet_key("invoice")
def api_tposs():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([tpos._asdict() for tpos in get_tposs(wallet_ids)]), HTTPStatus.OK


@tpos_ext.route("/api/v1/tposs", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "currency": {"type": "string", "empty": False, "required": True},
    }
)
def api_tpos_create():
    tpos = create_tpos(wallet_id=g.wallet.id, **g.data)

    return jsonify(tpos._asdict()), HTTPStatus.CREATED


@tpos_ext.route("/api/v1/tposs/<tpos_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
def api_tpos_delete(tpos_id):
    tpos = get_tpos(tpos_id)

    if not tpos:
        return jsonify({"message": "TPoS does not exist."}), HTTPStatus.NOT_FOUND

    if tpos.wallet != g.wallet.id:
        return jsonify({"message": "Not your TPoS."}), HTTPStatus.FORBIDDEN

    delete_tpos(tpos_id)

    return "", HTTPStatus.NO_CONTENT


@tpos_ext.route("/api/v1/tposs/<tpos_id>/invoices/", methods=["POST"])
@api_validate_post_request(schema={"amount": {"type": "integer", "min": 1, "required": True}})
def api_tpos_create_invoice(tpos_id):
    tpos = get_tpos(tpos_id)

    if not tpos:
        return jsonify({"message": "TPoS does not exist."}), HTTPStatus.NOT_FOUND

    try:
        checking_id, payment_request = create_invoice(
            wallet_id=tpos.wallet, amount=g.data["amount"], memo=f"#tpos {tpos.name}"
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), HTTPStatus.CREATED


@tpos_ext.route("/api/v1/tposs/<tpos_id>/invoices/<checking_id>", methods=["GET"])
def api_tpos_check_invoice(tpos_id, checking_id):
    tpos = get_tpos(tpos_id)

    if not tpos:
        return jsonify({"message": "TPoS does not exist."}), HTTPStatus.NOT_FOUND

    try:
        is_paid = not WALLET.get_invoice_status(checking_id).pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        wallet = get_wallet(tpos.wallet)
        payment = wallet.get_payment(checking_id)
        payment.set_pending(False)

        return jsonify({"paid": True}), HTTPStatus.OK

    return jsonify({"paid": False}), HTTPStatus.OK
