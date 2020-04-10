from flask import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.tpos import tpos_ext
from lnbits.helpers import Status
import requests
import json

from .crud import get_tpos


@tpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("tpos/index.html", user=g.user)


@tpos_ext.route("/<tpos_id>")
def tpos(tpos_id):
    tpos = get_tpos(tpos_id) or abort(Status.NOT_FOUND, "tpos does not exist.")
    print(tpos)
    r = requests.get("https://api.opennode.co/v1/rates")
    r_json = r.json()
    print(r_json["data"]["BTC" + tpos.currency][tpos.currency])

    return render_template("tpos/tpos.html", tpos=tpos, rate=r_json["data"]["BTC" + tpos.currency][tpos.currency])
