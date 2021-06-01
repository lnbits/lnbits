from quart import g, jsonify, request
from http import HTTPStatus
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl  # type: ignore
from base64 import urlsafe_b64encode
import base64
import json

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
    create_jukebox_payment,
    get_jukebox_payment,
    update_jukebox_payment,
)
from .models import Jukebox
from lnbits.core.services import create_invoice, check_invoice_status

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

######GET ACCESS TOKEN######


@jukebox_ext.route("/api/v1/jukebox/jb/playlist/<sp_id>/<sp_playlist>", methods=["GET"])
async def api_get_jukebox_son(sp_id, sp_playlist):
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
                        return await api_get_jukebox_son(sp_id, sp_playlist)
                return r, HTTPStatus.OK
            for item in r.json()["items"]:
                tracks.append(
                    {
                        'id': item["track"]["id"], 
                        'name': item["track"]["name"],
                        'album': item["track"]["album"]["name"],
                        'artist': item["track"]["artists"][0]["name"],
                        'image': item["track"]["album"]["images"][0]["url"]
                    }
                )
        except AssertionError:
            something = None
    return jsonify([track for track in tracks])

   # return jsonify([track for track in tracks])


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

@jukebox_ext.route("/api/v1/jukebox/jb/invoice/<sp_id>/<song_id>", methods=["GET"])
async def api_get_jukebox_invoice(sp_id, song_id):
    jukebox = await get_jukebox(sp_id)
    
    invoice = await create_invoice(wallet_id=jukebox.wallet,amount=jukebox.price,memo=jukebox.title)
    jukebox_payment = await create_jukebox_payment(song_id,invoice[0])
    print(jukebox_payment)
    
    ####new table needed to store payment hashes
    return jsonify(invoice, jukebox_payment)


@jukebox_ext.route("/api/v1/jukebox/jb/invoicecheck/<payment_hash>/<sp_id>", methods=["GET"])
async def api_get_jukebox_check_invoice(sp_id, payment_hash):
    jukebox = await get_jukebox(sp_id)
    status = await check_invoice_status(jukebox.wallet, payment_hash)
    is_paid = not status.pending
    if is_paid:
        jukebox_payment = await update_jukebox_payment(payment_hash, paid = True)
        print("https://api.spotify.com/v1/me/player/queue?uri=spotify%3Atrack%3A" + jukebox_payment.song_id + "&device_id=" + jukebox.sp_device)      
        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    "https://api.spotify.com/v1/me/player/queue?uri=spotify%3Atrack%3A" + jukebox_payment.song_id + "&device_id=" + jukebox.sp_device,
                    timeout=40,
                    headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                )
                if r.json()["error"]["status"] == 401:
                    token = await api_get_token(sp_id)
                    if token == False:
                        print("invalid")
                        return jsonify({"error": "Something went wrong"})
                    else:
                        return await api_get_jukebox_check_invoice(sp_id, payment_hash)
                if r.json()["error"]["status"] == 400:
                    return jsonify({"error": "Something went wrong"})
                
                return r, HTTPStatus.OK
            except AssertionError:
                something = None
                return jsonify({"error": "Something went wrong"})
    if not is_paid:
        return jsonify({"status": False})
    return jsonify({"error": "Something went wrong"})