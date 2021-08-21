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
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

@jukebox_ext.get("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index(request: Request):
    return await templates.TemplateResponse("jukebox/index.html", {"request": request,"user":g.user})


@jukebox_ext.get("/<juke_id>")
async def connect_to_jukebox(request: Request, juke_id):
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
        return await templates.TemplateResponse(
            "jukebox/jukebox.html",
            playlists=jukebox.sp_playlists.split(","),
            juke_id=juke_id,
            price=jukebox.price,
            inkey=jukebox.inkey,
        )
    else:
        return await templates.TemplateResponse("jukebox/error.html",{"request": request})
