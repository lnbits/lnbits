import time
from datetime import datetime
from quart import g, render_template, request, jsonify, websocket
from http import HTTPStatus
import trio
from lnbits.decorators import check_user_exists, validate_uuids
from lnbits.core.models import Payment

import json
from . import jukebox_ext
from .crud import get_jukebox
from .views_api import api_get_jukebox_device_check


@jukebox_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("jukebox/index.html", user=g.user)


@jukebox_ext.route("/<juke_id>")
async def connect_to_jukebox(juke_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        return "error"
    deviceCheck = await api_get_jukebox_device_check(juke_id)
    devices = json.loads(deviceCheck[0].text)
    deviceConnected = False
    for device in devices["devices"]:
        if device["id"] == jukebox.sp_device.split("-")[1]:
            deviceConnected = True
    if deviceConnected:
        return await render_template(
            "jukebox/jukebox.html",
            playlists=jukebox.sp_playlists.split(","),
            juke_id=juke_id,
            price=jukebox.price,
            inkey=jukebox.inkey,
        )
    else:
        return await render_template("jukebox/error.html")
