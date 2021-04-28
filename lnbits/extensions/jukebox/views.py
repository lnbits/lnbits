import time
from datetime import datetime
from quart import g, render_template, request
from http import HTTPStatus

from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.core.models import Payment
from lnbits.core.crud import get_standalone_payment

from . import jukebox_ext
from .crud import get_jukebox
from urllib.parse import unquote

@jukebox_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("jukebox/index.html", user=g.user)


@jukebox_ext.route("/<juke_id>")
async def print_qr_codes(juke_id):
    jukebox = await get_jukebox(juke_id)

    return await render_template("jukebox/jukebox.html", jukebox=jukebox)