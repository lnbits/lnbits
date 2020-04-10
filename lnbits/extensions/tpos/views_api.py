from flask import g, jsonify, request

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_macaroon, api_validate_post_request
from lnbits.helpers import Status

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
@api_validate_post_request(required_params=["name", "currency"])
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
        return jsonify({"message": "Not your tpos."}), Status.FORBIDDEN

    delete_tpos(tpos_id)

    return '', Status.NO_CONTENT

@tpos_ext.route("/api/v1/tposs/invoice/<tpos_id>", methods=["POST"])
@api_validate_post_request(required_params=["amount"])
def api_tpos_create_invoice(tpos_id):
    r = get_tpos(tpos_id)
    print(r)
    rr = get_wallet(tpos_id.id)
    print(rr)
  #  api_payments_create_invoice(memo=tpos_id.id, amount=amount, )

    return jsonify(rr), Status.CREATED

