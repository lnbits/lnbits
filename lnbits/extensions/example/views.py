from flask import g, render_template

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.example import example_ext


@example_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("example/index.html", user=g.user)
