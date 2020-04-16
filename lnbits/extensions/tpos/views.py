import requests

from flask import g, abort, render_template

from lnbits.core.crud import get_wallet
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.helpers import Status

from lnbits.extensions.tpos import tpos_ext
from .crud import get_tpos


@tpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("tpos/index.html", user=g.user)


@tpos_ext.route("/<tpos_id>")
def tpos(tpos_id):
    tpos = get_tpos(tpos_id) or abort(Status.NOT_FOUND, "tpos does not exist.")
    r = requests.get("https://api.opennode.co/v1/rates")
    r_json = r.json()
    rr = get_wallet(tpos.wallet)
    return render_template("tpos/tpos.html", tpos=tpos.id, inkey=rr.inkey, rate=r_json["data"]["BTC" + tpos.currency][tpos.currency], curr=tpos.currency)
