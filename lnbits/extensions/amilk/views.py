from flask import g, abort, render_template
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.amilk import amilk_ext

from .crud import get_amilk


@amilk_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():
    return render_template("amilk/index.html", user=g.user)


@amilk_ext.route("/<amilk_id>")
def wall(amilk_id):
    amilk = get_amilk(amilk_id) or abort(HTTPStatus.NOT_FOUND, "AMilk does not exist.")

    return render_template("amilk/wall.html", amilk=amilk)
