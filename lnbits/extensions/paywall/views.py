from flask import g, abort, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.paywall import paywall_ext
from lnbits.helpers import Status

from .crud import get_paywall


@paywall_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("paywall/index.html", user=g.user)


@paywall_ext.route("/<paywall_id>")
def wall(paywall_id):
    paywall = get_paywall(paywall_id) or abort(Status.NOT_FOUND, "Paywall does not exist.")

    return render_template("paywall/wall.html", paywall=paywall)
