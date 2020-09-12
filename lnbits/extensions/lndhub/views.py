from flask import render_template, g

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.lndhub import lndhub_ext


@lndhub_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def lndhub_index():
    return render_template("lndhub/index.html", user=g.user)
