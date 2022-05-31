from quart import g, jsonify, request
from http import HTTPStatus
import base64
from lnbits.core.crud import get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
import json

from lnbits.decorators import api_check_wallet_key, api_validate_post_request
import httpx
from . import jukebox_ext
from .crud import (
    create_jukebox,
    update_jukebox,
    get_jukebox,
    get_jukeboxs,
    delete_jukebox,
    create_jukebox_payment,
    get_jukebox_payment,
    update_jukebox_payment,
)
from lnbits.core.services import create_invoice, check_invoice_status


@jukebox_ext.route("/api/v1/jukebox", methods=["GET"])
@api_check_wallet_key("admin")
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
    sp_code = ""
    sp_access_token = ""
    sp_refresh_token = ""
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
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


@jukebox_ext.route("/api/v1/jukebox/<juke_id>", methods=["GET"])
@api_check_wallet_key("admin")
async def api_check_credentials_check(juke_id):
    jukebox = await get_jukebox(juke_id)
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
        "price": {"type": "string", "required": False},
    }
)
async def api_create_update_jukebox(juke_id=None):
    if juke_id:
        jukebox = await update_jukebox(juke_id=juke_id, inkey=g.wallet.inkey, **g.data)
    else:
        jukebox = await create_jukebox(inkey=g.wallet.inkey, **g.data)

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


@jukebox_ext.route(
    "/api/v1/jukebox/jb/playlist/<juke_id>/<sp_playlist>", methods=["GET"]
)
async def api_get_jukebox_song(juke_id, sp_playlist, retry=False):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    tracks = []
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                "https://api.spotify.com/v1/playlists/" + sp_playlist + "/tracks",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            if "items" not in r.json():
                if r.status_code == 401:
                    token = await api_get_token(juke_id)
                    if token == False:
                        return False
                    elif retry:
                        return (
                            jsonify({"error": "Failed to get auth"}),
                            HTTPStatus.FORBIDDEN,
                        )
                    else:
                        return await api_get_jukebox_song(
                            juke_id, sp_playlist, retry=True
                        )
                return r, HTTPStatus.OK
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
    return jsonify([track for track in tracks])


async def api_get_token(juke_id):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
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
                    juke_id=juke_id, sp_access_token=r.json()["access_token"]
                )
        except AssertionError:
            something = None
    return True


######CHECK DEVICE


@jukebox_ext.route("/api/v1/jukebox/jb/<juke_id>", methods=["GET"])
async def api_get_jukebox_device_check(juke_id, retry=False):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    async with httpx.AsyncClient() as client:
        rDevice = await client.get(
            "https://api.spotify.com/v1/me/player/devices",
            timeout=40,
            headers={"Authorization": "Bearer " + jukebox.sp_access_token},
        )

        if rDevice.status_code == 204 or rDevice.status_code == 200:
            return (
                rDevice,
                HTTPStatus.OK,
            )
        elif rDevice.status_code == 401 or rDevice.status_code == 403:
            token = await api_get_token(juke_id)
            if token == False:
                return (
                    jsonify({"error": "No device connected"}),
                    HTTPStatus.FORBIDDEN,
                )
            elif retry:
                return (
                    jsonify({"error": "Failed to get auth"}),
                    HTTPStatus.FORBIDDEN,
                )
            else:
                return api_get_jukebox_device_check(juke_id, retry=True)
        else:
            return (
                jsonify({"error": "No device connected"}),
                HTTPStatus.FORBIDDEN,
            )


######GET INVOICE STUFF


@jukebox_ext.route("/api/v1/jukebox/jb/invoice/<juke_id>/<song_id>", methods=["GET"])
async def api_get_jukebox_invoice(juke_id, song_id):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    try:
        deviceCheck = await api_get_jukebox_device_check(juke_id)
        devices = json.loads(deviceCheck[0].text)
        deviceConnected = False
        for device in devices["devices"]:
            if device["id"] == jukebox.sp_device.split("-")[1]:
                deviceConnected = True
        if not deviceConnected:
            return (
                jsonify({"error": "No device connected"}),
                HTTPStatus.NOT_FOUND,
            )
    except:
        return (
            jsonify({"error": "No device connected"}),
            HTTPStatus.NOT_FOUND,
        )

    invoice = await create_invoice(
        wallet_id=jukebox.wallet,
        amount=jukebox.price,
        memo=jukebox.title,
        extra={"tag": "jukebox"},
    )

    jukebox_payment = await create_jukebox_payment(song_id, invoice[0], juke_id)

    return jsonify(invoice, jukebox_payment)


@jukebox_ext.route(
    "/api/v1/jukebox/jb/checkinvoice/<pay_hash>/<juke_id>", methods=["GET"]
)
async def api_get_jukebox_invoice_check(pay_hash, juke_id):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    try:
        status = await check_invoice_status(jukebox.wallet, pay_hash)
        is_paid = not status.pending
    except Exception as exc:
        return jsonify({"paid": False}), HTTPStatus.OK
    if is_paid:
        wallet = await get_wallet(jukebox.wallet)
        payment = await wallet.get_payment(pay_hash)
        await payment.set_pending(False)
        await update_jukebox_payment(pay_hash, paid=True)
        return jsonify({"paid": True}), HTTPStatus.OK
    return jsonify({"paid": False}), HTTPStatus.OK


@jukebox_ext.route(
    "/api/v1/jukebox/jb/invoicep/<song_id>/<juke_id>/<pay_hash>", methods=["GET"]
)
async def api_get_jukebox_invoice_paid(song_id, juke_id, pay_hash, retry=False):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    await api_get_jukebox_invoice_check(pay_hash, juke_id)
    jukebox_payment = await get_jukebox_payment(pay_hash)
    if jukebox_payment.paid:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://api.spotify.com/v1/me/player/currently-playing?market=ES",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            rDevice = await client.get(
                "https://api.spotify.com/v1/me/player",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            isPlaying = False
            if rDevice.status_code == 200:
                isPlaying = rDevice.json()["is_playing"]

            if r.status_code == 204 or isPlaying == False:
                async with httpx.AsyncClient() as client:
                    uri = ["spotify:track:" + song_id]
                    r = await client.put(
                        "https://api.spotify.com/v1/me/player/play?device_id="
                        + jukebox.sp_device.split("-")[1],
                        json={"uris": uri},
                        timeout=40,
                        headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                    )
                    if r.status_code == 204:
                        return jsonify(jukebox_payment), HTTPStatus.OK
                    elif r.status_code == 401 or r.status_code == 403:
                        token = await api_get_token(juke_id)
                        if token == False:
                            return (
                                jsonify({"error": "Invoice not paid"}),
                                HTTPStatus.FORBIDDEN,
                            )
                        elif retry:
                            return (
                                jsonify({"error": "Failed to get auth"}),
                                HTTPStatus.FORBIDDEN,
                            )
                        else:
                            return api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash, retry=True
                            )
                    else:
                        return (
                            jsonify({"error": "Invoice not paid"}),
                            HTTPStatus.FORBIDDEN,
                        )
            elif r.status_code == 200:
                async with httpx.AsyncClient() as client:
                    r = await client.post(
                        "https://api.spotify.com/v1/me/player/queue?uri=spotify%3Atrack%3A"
                        + song_id
                        + "&device_id="
                        + jukebox.sp_device.split("-")[1],
                        timeout=40,
                        headers={"Authorization": "Bearer " + jukebox.sp_access_token},
                    )
                    if r.status_code == 204:
                        return jsonify(jukebox_payment), HTTPStatus.OK

                    elif r.status_code == 401 or r.status_code == 403:
                        token = await api_get_token(juke_id)
                        if token == False:
                            return (
                                jsonify({"error": "Invoice not paid"}),
                                HTTPStatus.OK,
                            )
                        elif retry:
                            return (
                                jsonify({"error": "Failed to get auth"}),
                                HTTPStatus.FORBIDDEN,
                            )
                        else:
                            return await api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash
                            )
                    else:
                        return (
                            jsonify({"error": "Invoice not paid"}),
                            HTTPStatus.OK,
                        )
            elif r.status_code == 401 or r.status_code == 403:
                token = await api_get_token(juke_id)
                if token == False:
                    return (
                        jsonify({"error": "Invoice not paid"}),
                        HTTPStatus.OK,
                    )
                elif retry:
                    return (
                        jsonify({"error": "Failed to get auth"}),
                        HTTPStatus.FORBIDDEN,
                    )
                else:
                    return await api_get_jukebox_invoice_paid(
                        song_id, juke_id, pay_hash
                    )
    return jsonify({"error": "Invoice not paid"}), HTTPStatus.OK


############################GET TRACKS


@jukebox_ext.route("/api/v1/jukebox/jb/currently/<juke_id>", methods=["GET"])
async def api_get_jukebox_currently(juke_id, retry=False):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        return (
            jsonify({"error": "No Jukebox"}),
            HTTPStatus.FORBIDDEN,
        )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                "https://api.spotify.com/v1/me/player/currently-playing?market=ES",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            if r.status_code == 204:
                return jsonify({"error": "Nothing"}), HTTPStatus.OK
            elif r.status_code == 200:
                try:
                    response = r.json()

                    track = {
                        "id": response["item"]["id"],
                        "name": response["item"]["name"],
                        "album": response["item"]["album"]["name"],
                        "artist": response["item"]["artists"][0]["name"],
                        "image": response["item"]["album"]["images"][0]["url"],
                    }
                    return jsonify(track), HTTPStatus.OK
                except:
                    return jsonify("Something went wrong"), HTTPStatus.NOT_FOUND

            elif r.status_code == 401:
                token = await api_get_token(juke_id)
                if token == False:
                    return (
                        jsonify({"error": "Invoice not paid"}),
                        HTTPStatus.FORBIDDEN,
                    )
                elif retry:
                    return (
                        jsonify({"error": "Failed to get auth"}),
                        HTTPStatus.FORBIDDEN,
                    )
                else:
                    return await api_get_jukebox_currently(juke_id, retry=True)
            else:
                return jsonify("Something went wrong"), HTTPStatus.NOT_FOUND
        except AssertionError:
            return jsonify("Something went wrong"), HTTPStatus.NOT_FOUND
