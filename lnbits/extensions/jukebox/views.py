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
from urllib.parse import unquote


@jukebox_ext.route("/")
@validate_uuids(["usr"], required=True)
@check_user_exists()
async def index():
    return await render_template("jukebox/index.html", user=g.user)


@jukebox_ext.route("/<juke_id>")
async def print_qr_codes(juke_id):
    jukebox = await get_jukebox(juke_id)
    if not jukebox:
        return "error"

    return await render_template(
        "jukebox/jukebox.html",
        playlists=jukebox.sp_playlists.split(","),
        juke_id=juke_id,
        price=jukebox.price,
        inkey=jukebox.inkey,
    )


##################WEBSOCKET ROUTES########################


connected_websockets = set()


def collect_websocket(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global connected_websockets
        send_channel, receive_channel = trio.open_memory_channel(0)
        connected_websockets.add(send_channel)
        try:
            return await func(receive_channel, *args, **kwargs)
        finally:
            connected_websockets.remove(send_channel)

    return wrapper


@jukebox_ext.websocket("/ws")
@collect_websocket
async def wss(receive_channel):
    while True:
        data = await receive_channel.receive()
        await websocket.send(data)


async def broadcast(message):
    print(connected_websockets)
    for queue in connected_websockets:
        await queue.send(f"{message}")
