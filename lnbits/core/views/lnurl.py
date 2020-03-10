import requests

from flask import abort, redirect, request, url_for
from lnurl import LnurlWithdrawResponse, handle as handle_lnurl
from lnurl.exceptions import LnurlException
from time import sleep

from lnbits.core import core_app
from lnbits.helpers import Status
from lnbits.settings import WALLET

from ..crud import create_account, get_user, create_wallet, create_payment


@core_app.route("/lnurlwallet")
def lnurlwallet():
    try:
        withdraw_res = handle_lnurl(request.args.get("lightning"), response_class=LnurlWithdrawResponse)
    except LnurlException:
        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    _, payhash, payment_request = WALLET.create_invoice(withdraw_res.max_sats, "LNbits LNURL funding")

    r = requests.get(
        withdraw_res.callback.base,
        params={**withdraw_res.callback.query_params, **{"k1": withdraw_res.k1, "pr": payment_request}},
    )

    if not r.ok:
        abort(Status.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    for i in range(10):
        r = WALLET.get_invoice_status(payhash).raw_response
        sleep(i)
        if not r.ok:
            continue
        break

    user = get_user(create_account().id)
    wallet = create_wallet(user_id=user.id)
    create_payment(  # TODO: not pending?
        wallet_id=wallet.id, payhash=payhash, amount=withdraw_res.max_sats * 1000, memo="LNbits lnurl funding"
    )

    return redirect(url_for("core.wallet", usr=user.id, wal=wallet.id))
