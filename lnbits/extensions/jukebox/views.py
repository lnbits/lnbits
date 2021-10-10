import json
import time
from datetime import datetime
from http import HTTPStatus
from lnbits.decorators import check_user_exists
from . import jukebox_ext, jukebox_renderer
from .crud import get_jukebox
from fastapi import FastAPI, Request
from fastapi.params import Depends
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from lnbits.core.models import User, Payment


@jukebox_ext.get("/", response_class=HTMLResponse)
async def index(request: Request, user: User = Depends(check_user_exists)):
    return jukebox_renderer().TemplateResponse(
        "jukebox/index.html", {"request": request, "user": user.dict()}
    )


@jukebox_ext.get("/{juke_id}", response_class=HTMLResponse)
async def connect_to_jukebox(request: Request, juke_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Jukebox does not exist."
        )
    deviceCheck = await api_get_jukebox_device_check(juke_id)
    devices = json.loads(deviceCheck[0].text)
    deviceConnected = False
    for device in devices["devices"]:
        if device["id"] == jukebox.sp_device.split("-")[1]:
            deviceConnected = True
    if deviceConnected:
        return jukebox_renderer().TemplateResponse(
            "jukebox/display.html",
            {
                "request": request,
                "playlists": jukebox.sp_playlists.split(","),
                "juke_id": juke_id,
                "price": jukebox.price,
                "inkey": jukebox.inkey,
            },
        )
    else:
        return jukebox_renderer().TemplateResponse(
            "jukebox/error.html", {"request": request}
        )
