from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
import httpx
from . import jukebox_ext
from .crud import (
    create_jukebox,
    update_jukebox,
    get_jukebox,
    get_jukebox_by_user,
    get_jukeboxs,
    delete_jukebox,
)
from .models import Jukebox


@jukebox_ext.route("/api/v1/jukebox", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_jukeboxs():
    jsonify([jukebox._asdict() for jukebox in await get_jukeboxs(g.wallet.id)]),


##################SPOTIFY AUTH#####################


@jukebox_ext.route("/api/v1/jukebox/spotify/cb/<sp_user>/", methods=["GET"])
async def api_check_credentials_callbac(sp_user):
    jukebox = await get_jukebox_by_user(sp_user)
    jukebox = await update_jukebox(
        sp_user=sp_user, sp_secret=jukebox.sp_secret, sp_token=request.args.get('code')
    )
    return "<h1>Success!</h1><h2>You can close this window</h2>"

@jukebox_ext.route("/api/v1/jukebox/spotify/<sp_user>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_check_credentials_check(sp_user):
    jukebox = await get_jukebox_by_user(sp_user)
    return jsonify(jukebox._asdict()), HTTPStatus.CREATED


@jukebox_ext.route("/api/v1/jukebox/", methods=["POST"])
@jukebox_ext.route("/api/v1/jukebox/<item_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "title": {"type": "string", "empty": False, "required": True},
        "wallet": {"type": "string", "empty": False, "required": True},
        "sp_user": {"type": "string", "empty": False, "required": True},
        "sp_secret": {"type": "string", "required": True},
        "sp_token": {"type": "string", "required": False},
        "sp_device": {"type": "string", "required": False},
        "sp_playlists": {"type": "string", "required": False},
        "price": {"type": "string", "required": True},
    }
)
async def api_create_update_jukebox(item_id=None):
    print(g.data)
    jukebox = await create_jukebox(**g.data)
    return jsonify(jukebox._asdict()), HTTPStatus.CREATED


@jukebox_ext.route("/api/v1/jukebox/<juke_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_delete_item(juke_id):
    shop = await delete_jukebox(juke_id)
    return "", HTTPStatus.NO_CONTENT
