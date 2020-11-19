from quart import g, render_template, request, redirect
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.core.models import Payment
from lnbits.core.crud import get_wallet_payment

from . import livestream_ext
from .crud import get_track, get_livestream_by_track


@livestream_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("livestream/index.html", user=g.user)


@livestream_ext.route("/track/<track_id>")
async def track_redirect_download(track_id):
    payment_hash = request.args.get("p")
    track = await get_track(track_id)
    ls = await get_livestream_by_track(track_id)
    payment: Payment = await get_wallet_payment(ls.wallet, payment_hash)

    if not payment:
        return f"Couldn't find the payment {payment_hash} or track {track.id}.", HTTPStatus.NOT_FOUND

    if payment.pending:
        return f"Payment {payment_hash} wasn't received yet. Please try again in a minute.", HTTPStatus.PAYMENT_REQUIRED

    return redirect(track.download_url)
