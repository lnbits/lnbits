from flask import g, abort, render_template, jsonify
import json
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.extensions.usermanager import usermanager_ext
from lnbits.helpers import Status
from lnbits.db import open_ext_db


@usermanager_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
def index():

    return render_template("usermanager/index.html", user=g.user)