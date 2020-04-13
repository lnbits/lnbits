from flask import g, jsonify, request

from lnbits.core.crud import get_user
from lnbits.core.utils import create_invoice
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status
from lnbits.settings import WALLET, FEE_RESERVE
from lnbits.extensions.tpos import tpos_ext

from .crud import create_tpos, get_tpos, get_tposs, delete_tpos

@tpos_ext.route("/api/v1/tposs", methods=["GET"])
@api_check_wallet_macaroon(key_type="invoice")
def api_tposs():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([tpos._asdict() for tpos in get_tposs(wallet_ids)]), Status.OK


@tpos_ext.route("/api/v1/tposs", methods=["POST"])
@api_check_wallet_macaroon(key_type="invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "currency": {"type": "string", "empty": False, "required": True},
    }
)
def api_tpos_create():
    print("poo")

    tpos = create_tpos(wallet_id=g.wallet.id, name=g.data["name"], currency=g.data["currency"])

    return jsonify(tpos._asdict()), Status.CREATED


@tpos_ext.route("/api/v1/tposs/<tpos_id>", methods=["DELETE"])
@api_check_wallet_macaroon(key_type="invoice")
def api_tpos_delete(tpos_id):
    tpos = get_tpos(tpos_id)

    if not tpos:
        return jsonify({"message": "TPoS does not exist."}), Status.NOT_FOUND

    if tpos.wallet != g.wallet.id:
        return jsonify({"message": "Not your TPoS."}), Status.FORBIDDEN

    delete_tpos(tpos_id)

    return '', Status.NO_CONTENT


@tpos_ext.route("/api/v1/tposs/invoice/<tpos_id>", methods=["POST"])
@api_validate_post_request(schema={"amount": {"type": "integer", "min": 1, "required": True}})
def api_tpos_create_invoice(tpos_id):

    tpos = get_tpos(tpos_id)
    
    if not tpos:
        return jsonify({"message": "TPoS does not exist."}), Status.NOT_FOUND
    try:
        memo = f"TPoS {tpos_id}"
        checking_id, payment_request = create_invoice(wallet_id=tpos.wallet, amount=g.data["amount"], memo=memo)
    
    except Exception as e:
        return jsonify({"message": str(e)}), Status.INTERNAL_SERVER_ERROR

    return jsonify({"checking_id": checking_id, "payment_request": payment_request}), Status.OK

@tpos_ext.route("/api/v1/tposs/invoice/<checking_id>", methods=["GET"])
def api_tpos_check_invoice(checking_id):
    print(checking_id)
    PAID = WALLET.get_invoice_status(checking_id).paid
    
    if PAID == True:
        return jsonify({"PAID": True}), Status.OK
    return jsonify({"PAID": False}), Status.OK
