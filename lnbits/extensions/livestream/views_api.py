from quart import g, jsonify
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore

from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import livestream_ext
from .crud import (
    get_or_create_livestream_by_wallet,
    add_track,
    get_tracks,
    update_track,
    add_producer,
    get_producers,
    update_current_track,
    update_livestream_fee,
    delete_track_from_livestream,
)


@livestream_ext.route("/api/v1/livestream", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_livestream_from_wallet():
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    tracks = await get_tracks(ls.id)
    producers = await get_producers(ls.id)

    try:
        return (
            jsonify(
                {
                    **ls._asdict(),
                    **{
                        "lnurl": ls.lnurl,
                        "tracks": [
                            dict(lnurl=track.lnurl, **track._asdict())
                            for track in tracks
                        ],
                        "producers": [producer._asdict() for producer in producers],
                    },
                }
            ),
            HTTPStatus.OK,
        )
    except LnurlInvalidUrl:
        return (
            jsonify(
                {
                    "message": "LNURLs need to be delivered over a publically accessible `https` domain or Tor."
                }
            ),
            HTTPStatus.UPGRADE_REQUIRED,
        )


@livestream_ext.route("/api/v1/livestream/track/<track_id>", methods=["PUT"])
@api_check_wallet_key("invoice")
async def api_update_track(track_id):
    try:
        id = int(track_id)
    except ValueError:
        id = 0
    if id <= 0:
        id = None

    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    await update_current_track(ls.id, id)
    return "", HTTPStatus.NO_CONTENT


@livestream_ext.route("/api/v1/livestream/fee/<fee_pct>", methods=["PUT"])
@api_check_wallet_key("invoice")
async def api_update_fee(fee_pct):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    await update_livestream_fee(ls.id, int(fee_pct))
    return "", HTTPStatus.NO_CONTENT


@livestream_ext.route("/api/v1/livestream/tracks", methods=["POST"])
@livestream_ext.route("/api/v1/livestream/tracks/<id>", methods=["PUT"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "name": {"type": "string", "empty": False, "required": True},
        "download_url": {"type": "string", "empty": False, "required": False},
        "price_msat": {"type": "number", "min": 0, "required": False},
        "producer_id": {
            "type": "number",
            "required": True,
            "excludes": "producer_name",
        },
        "producer_name": {
            "type": "string",
            "required": True,
            "excludes": "producer_id",
        },
    }
)
async def api_add_track(id=None):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)

    if "producer_id" in g.data:
        p_id = g.data["producer_id"]
    elif "producer_name" in g.data:
        p_id = await add_producer(ls.id, g.data["producer_name"])
    else:
        raise TypeError("need either producer_id or producer_name arguments")

    if id:
        await update_track(
            ls.id,
            id,
            g.data["name"],
            g.data.get("download_url"),
            g.data.get("price_msat", 0),
            p_id,
        )
        return "", HTTPStatus.OK
    else:
        await add_track(
            ls.id,
            g.data["name"],
            g.data.get("download_url"),
            g.data.get("price_msat", 0),
            p_id,
        )
        return "", HTTPStatus.CREATED


@livestream_ext.route("/api/v1/livestream/tracks/<track_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_delete_track(track_id):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    await delete_track_from_livestream(ls.id, track_id)
    return "", HTTPStatus.NO_CONTENT
