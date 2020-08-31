import json

from flask import g, abort, render_template, jsonify

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.diagonalley import diagonalley_ext
from lnbits.db import open_ext_db


@diagonalley_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():

    return render_template("diagonalley/index.html", user=g.user)
