from quart import g, jsonify
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import jukebox_ext
from .crud import (
    create_update_jukebox,
    get_jukebox,
    get_jukeboxs,
    delete_jukebox,
)
from .models import Jukebox


@jukebox_ext.route("/api/v1/jukebox", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_jukeboxs():
    jukebox = await get_jukeboxs(g.wallet.id)
    return (
        jsonify(
            {
                jukebox._asdict()
            }
        ),
        HTTPStatus.OK,
    )

#websocket get spotify crap

@jukebox_ext.route("/api/v1/jukebox/items", methods=["POST"])
@jukebox_ext.route("/api/v1/jukebox/items/<item_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(

    schema={
        "wallet": {"type": "string", "empty": False},
        "user": {"type": "string", "empty": False},
        "secret": {"type": "string", "required": False},
        "token": {"type": "string", "required": True},
        "playlists": {"type": "string", "required": True},
    }
)
async def api_create_update_jukebox(item_id=None):
    jukebox = await create_update_jukebox(g.wallet.id, **g.data)
    return jsonify(jukebox._asdict()), HTTPStatus.CREATED


@jukebox_ext.route("/api/v1/jukebox/<juke_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_delete_item(juke_id):
    shop = await delete_jukebox(juke_id)
    return "", HTTPStatus.NO_CONTENT