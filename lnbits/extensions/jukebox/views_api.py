from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from base64 import urlsafe_b64encode
import base64

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
from lnbits.core.services import create_invoice

@jukebox_ext.route("/api/v1/jukebox", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_get_jukeboxs():
    try:
        return (
            jsonify(
                [{**jukebox._asdict()} for jukebox in await get_jukeboxs(g.wallet.user)]
            ),
            HTTPStatus.OK,
        )
    except:
        return "", HTTPStatus.NO_CONTENT


##################SPOTIFY AUTH#####################


@jukebox_ext.route("/api/v1/jukebox/spotify/cb/<juke_id>", methods=["GET"])
async def api_check_credentials_callbac(juke_id):
    print(request.args)
    sp_code = ""
    sp_access_token = ""
    sp_refresh_token = ""
    jukebox = await get_jukebox(juke_id)
    if request.args.get("code"):
        sp_code = request.args.get("code")
        jukebox = await update_jukebox(
            juke_id=juke_id, sp_secret=jukebox.sp_secret, sp_access_token=sp_code
        )
    if request.args.get("access_token"):
        sp_access_token = request.args.get("access_token")
        sp_refresh_token = request.args.get("refresh_token")
        jukebox = await update_jukebox(
            juke_id=juke_id,
            sp_secret=jukebox.sp_secret,
            sp_access_token=sp_access_token,
            sp_refresh_token=sp_refresh_token,
        )
    return "<h1>Success!</h1><h2>You can close this window</h2>"


@jukebox_ext.route("/api/v1/jukebox/spotify/<sp_id>", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_check_credentials_check(sp_id):
    jukebox = await get_jukebox(sp_id)
    return jsonify(jukebox._asdict()), HTTPStatus.CREATED


@jukebox_ext.route("/api/v1/jukebox/", methods=["POST"])
@jukebox_ext.route("/api/v1/jukebox/<juke_id>", methods=["PUT"])
@api_check_wallet_key("admin")
@api_validate_post_request(
    schema={
        "user": {"type": "string", "empty": False, "required": True},
        "title": {"type": "string", "empty": False, "required": True},
        "wallet": {"type": "string", "empty": False, "required": True},
        "sp_user": {"type": "string", "empty": False, "required": True},
        "sp_secret": {"type": "string", "required": True},
        "sp_access_token": {"type": "string", "required": False},
        "sp_refresh_token": {"type": "string", "required": False},
        "sp_device": {"type": "string", "required": False},
        "sp_playlists": {"type": "string", "required": False},
        "price": {"type": "string", "required": True},
    }
)
async def api_create_update_jukebox(juke_id=None):
    if juke_id:
        jukebox = await update_jukebox(juke_id=juke_id, **g.data)
    else:
        jukebox = await create_jukebox(**g.data)
    return jsonify(jukebox._asdict()), HTTPStatus.CREATED


@jukebox_ext.route("/api/v1/jukebox/<juke_id>", methods=["DELETE"])
@api_check_wallet_key("admin")
async def api_delete_item(juke_id):
    await delete_jukebox(juke_id)
    try:
        return (
            jsonify(
                [{**jukebox._asdict()} for jukebox in await get_jukeboxs(g.wallet.user)]
            ),
            HTTPStatus.OK,
        )
    except:
        return "", HTTPStatus.NO_CONTENT


################JUKEBOX ENDPOINTS##################


@jukebox_ext.route("/api/v1/jukebox/jb/<sp_id>/<sp_playlist>", methods=["GET"])
async def api_get_jukebox_songs(sp_id, sp_playlist):
    jukebox = await get_jukebox(sp_id)
    tracks = []
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                "https://api.spotify.com/v1/playlists/" + sp_playlist + "/tracks",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            if "items" not in r.json():
                if r.json()["error"]["status"] == 401:
                    token = await api_get_token(sp_id)
                    if token == False:
                        print("invalid")
                        return False
                    else:
                        return await api_get_jukebox_songs(sp_id, sp_playlist)
            for item in r.json()["items"]:
                tracks.append(
                    {
                        "id": item["track"]["id"],
                        "name": item["track"]["name"],
                        "album": item["track"]["album"]["name"],
                        "artist": item["track"]["artists"][0]["name"],
                        "image": item["track"]["album"]["images"][0]["url"],
                    }
                )
        except AssertionError:
            something = None
    print(jsonify(tracks))
    return tracks, HTTPStatus.OK


async def api_get_token(sp_id):
    jukebox = await get_jukebox(sp_id)
    print(
        "Authorization: Bearer "
        + base64.b64encode(
            str(jukebox.sp_user + ":" + jukebox.sp_secret).encode("ascii")
        ).decode("ascii")
    )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(
                "https://accounts.spotify.com/api/token",
                timeout=40,
                params={
                    "grant_type": "refresh_token",
                    "refresh_token": jukebox.sp_refresh_token,
                    "client_id": jukebox.sp_user,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Basic "
                    + base64.b64encode(
                        str(jukebox.sp_user + ":" + jukebox.sp_secret).encode("ascii")
                    ).decode("ascii"),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            if "access_token" not in r.json():
                return False
            else:
                await update_jukebox(
                    juke_id=sp_id, sp_access_token=r.json()["access_token"]
                )
        except AssertionError:
            something = None
    return True


######GET INVOICE


@jukebox_ext.route("/api/v1/jukebox/jb/<sp_id>/<sp_song>/", methods=["GET"])
async def api_get_jukebox_invoice(sp_id, sp_song):
    jukebox = await get_jukebox(sp_id)
    invoice = await create_invoice(wallet_id=jukebox.wallet,amount=jukebox.amount,memo="Jukebox " + jukebox.name)

    return invoice, HTTPStatus.OK
