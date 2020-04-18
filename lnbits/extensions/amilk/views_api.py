from flask import g, jsonify, request

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.helpers import Status

from lnbits.extensions.amilk import amilk_ext
from .crud import create_amilk, get_amilk, get_amilks, delete_amilk
from lnbits.core.services import create_invoice

from flask import abort, redirect, request, url_for
from lnurl import LnurlWithdrawResponse, handle as handle_lnurl
from lnurl.exceptions import LnurlException
from time import sleep
import requests
from lnbits.settings import WALLET

@amilk_ext.route("/api/v1/amilk", methods=["GET"])
@api_check_wallet_key("invoice")
def api_amilks():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = get_user(g.wallet.user).wallet_ids

    return jsonify([amilk._asdict() for amilk in get_amilks(wallet_ids)]), Status.OK


@amilk_ext.route("/api/v1/amilk/milk/<amilk_id>", methods=["GET"])
def api_amilkit(amilk_id):
    milk = get_amilk(amilk_id)
    memo = milk.id

    try:
        withdraw_res = handle_lnurl(milk.lnurl, response_class=LnurlWithdrawResponse)
    except LnurlException:
        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")
    print(withdraw_res.max_sats)

    
    try:
        checking_id, payment_request = create_invoice(wallet_id=milk.wallet, amount=withdraw_res.max_sats, memo=memo)
        #print(payment_request)
    except Exception as e:
        error_message = False, str(e)

    r = requests.get(
        withdraw_res.callback.base,
        params={**withdraw_res.callback.query_params, **{"k1": withdraw_res.k1, "pr": payment_request}},
    )
    
    if not r.ok:

        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    for i in range(10):
        invoice_status = WALLET.get_invoice_status(checking_id)
        sleep(i)
        if not invoice_status.paid:
            continue
        else:
            return jsonify({"paid": False}), Status.OK
        break

    return jsonify({"paid": True}), Status.OK


@amilk_ext.route("/api/v1/amilk", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(schema={
    "lnurl": {"type": "string", "empty": False, "required": True},
    "atime": {"type": "integer", "min": 0, "required": True},
    "amount": {"type": "integer", "min": 0, "required": True},
})
def api_amilk_create():
    amilk = create_amilk(wallet_id=g.wallet.id, lnurl=g.data["lnurl"], atime=g.data["atime"], amount=g.data["amount"])

    return jsonify(amilk._asdict()), Status.CREATED


@amilk_ext.route("/api/v1/amilk/<amilk_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
def api_amilk_delete(amilk_id):
    amilk = get_amilk(amilk_id)

    if not amilk:
        return jsonify({"message": "Paywall does not exist."}), Status.NOT_FOUND

    if amilk.wallet != g.wallet.id:
        return jsonify({"message": "Not your amilk."}), Status.FORBIDDEN

    delete_amilk(amilk_id)

    return "", Status.NO_CONTENT
