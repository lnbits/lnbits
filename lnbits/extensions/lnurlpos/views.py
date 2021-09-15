from quart import g, abort, render_template, jsonify, websocket
from http import HTTPStatus
import httpx
from collections import defaultdict
from lnbits.decorators import check_user_exists, validate_uuids
from . import lnurlpos_ext
from .crud import get_lnurlpos
from quart import g, abort, render_template, jsonify, websocket
from functools import wraps
import trio
import shortuuid
from . import lnurlpos_ext


@lnurlpos_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("lnurlpos/index.html", user=g.user)

@lnurlpos_ext.route("/pos_id/<amount_pin>")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    #search for invoice via pin, if its paid decrypt and show pin
    return await render_template("lnurlpos/paid.html", pin=pin)
