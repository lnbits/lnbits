from fastapi import Request
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
import base64
from lnbits.core.crud import get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
import json
from typing import Optional
from fastapi.params import Depends
from fastapi.param_functions import Query
from .models import CreateJukeLinkData
from lnbits.decorators import (
    check_user_exists,
    WalletTypeInfo,
    get_key_type,
    api_validate_post_request,
)
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


@jukebox_ext.get("/api/v1/jukebox")
async def api_get_jukeboxs(
    req: Request,
    wallet: WalletTypeInfo = Depends(get_key_type),
    all_wallets: bool = Query(False),
):
    wallet_user = wallet.wallet.user

    try:
        return [
            {**jukebox.dict(), "jukebox": jukebox.jukebox(req)}
            for jukebox in await get_jukeboxs(wallet_user)
        ]

    except:
        raise HTTPException(
            status_code=HTTPStatus.NO_CONTENT,
            detail="No Jukeboxes",
        )


##################SPOTIFY AUTH#####################


@jukebox_ext.get("/api/v1/jukebox/spotify/cb/<juke_id>")
async def api_check_credentials_callbac(
    juke_id: str = Query(None),
    code: str = Query(None),
    access_token: str = Query(None),
    refresh_token: str = Query(None),
):
    sp_code = ""
    sp_access_token = ""
    sp_refresh_token = ""
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(detail="No Jukebox", status_code=HTTPStatus.FORBIDDEN)
    if code:
        sp_code = code
        jukebox = await update_jukebox(
            juke_id=juke_id, sp_secret=jukebox.sp_secret, sp_access_token=sp_code
        )
    if access_token:
        sp_access_token = access_token
        sp_refresh_token = refresh_token
        jukebox = await update_jukebox(
            juke_id=juke_id,
            sp_secret=jukebox.sp_secret,
            sp_access_token=sp_access_token,
            sp_refresh_token=sp_refresh_token,
        )
    return "<h1>Success!</h1><h2>You can close this window</h2>"


@jukebox_ext.get("/api/v1/jukebox/{juke_id}")
async def api_check_credentials_check(
    juke_id: str = Query(None), wallet: WalletTypeInfo = Depends(get_key_type)
):
    print(juke_id)
    jukebox = await get_jukebox(juke_id)

    return jukebox


@jukebox_ext.post("/api/v1/jukebox", status_code=HTTPStatus.CREATED)
@jukebox_ext.put("/api/v1/jukebox/{juke_id}", status_code=HTTPStatus.OK)
async def api_create_update_jukebox(
    data: CreateJukeLinkData,
    juke_id: str = Query(None),
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    if juke_id:
        jukebox = await update_jukebox(juke_id=juke_id, inkey=g.wallet.inkey, **g.data)
    else:
        jukebox = await create_jukebox(inkey=g.wallet.inkey, **g.data)

    return jukebox.dict()


@jukebox_ext.delete("/api/v1/jukebox/{juke_id}")
async def api_delete_item(
    juke_id=None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    await delete_jukebox(juke_id)
    try:
        return [{**jukebox.dict()} for jukebox in await get_jukeboxs(g.wallet.user)]
    except:
        raise HTTPException(
            status_code=HTTPStatus.NO_CONTENT,
            detail="No Jukebox",
        )


################JUKEBOX ENDPOINTS##################

######GET ACCESS TOKEN######


@jukebox_ext.get("/api/v1/jukebox/jb/playlist/{juke_id}/{sp_playlist}")
async def api_get_jukebox_song(
    juke_id: str = Query(None),
    sp_playlist: str = Query(None),
    retry: bool = Query(False),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No Jukeboxes",
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
                        raise HTTPException(
                            status_code=HTTPStatus.FORBIDDEN,
                            detail="Failed to get auth",
                        )
                    else:
                        return await api_get_jukebox_song(
                            juke_id, sp_playlist, retry=True
                        )
                return r
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
        except:
            something = None
    return [track for track in tracks]


async def api_get_token(juke_id=None):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No Jukeboxes",
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
        except:
            something = None
    return True


######CHECK DEVICE


@jukebox_ext.get("/api/v1/jukebox/jb/{juke_id}")
async def api_get_jukebox_device_check(
    juke_id: str = Query(None),
    retry: bool = Query(False),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No Jukeboxes",
        )
    async with httpx.AsyncClient() as client:
        rDevice = await client.get(
            "https://api.spotify.com/v1/me/player/devices",
            timeout=40,
            headers={"Authorization": "Bearer " + jukebox.sp_access_token},
        )

        if rDevice.status_code == 204 or rDevice.status_code == 200:
            return rDevice
        elif rDevice.status_code == 401 or rDevice.status_code == 403:
            token = await api_get_token(juke_id)
            if token == False:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="No devices connected",
                )
            elif retry:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="Failed to get auth",
                )
            else:
                return api_get_jukebox_device_check(juke_id, retry=True)
        else:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="No device connected",
            )


######GET INVOICE STUFF


@jukebox_ext.get("/api/v1/jukebox/jb/invoice/{juke_id}/{song_id}")
async def api_get_jukebox_invoice(
    juke_id: str = Query(None),
    song_id: str = Query(None),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No jukebox",
        )
    try:
        deviceCheck = await api_get_jukebox_device_check(juke_id)
        devices = json.loads(deviceCheck[0].text)
        deviceConnected = False
        for device in devices["devices"]:
            if device["id"] == jukebox.sp_device.split("-")[1]:
                deviceConnected = True
        if not deviceConnected:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="No device connected",
            )
    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="No device connected",
        )

    invoice = await create_invoice(
        wallet_id=jukebox.wallet,
        amount=jukebox.price,
        memo=jukebox.title,
        extra={"tag": "jukebox"},
    )

    jukebox_payment = await create_jukebox_payment(song_id, invoice[0], juke_id)

    return {invoice, jukebox_payment}


@jukebox_ext.get("/api/v1/jukebox/jb/checkinvoice/{pay_hash}/{juke_id}")
async def api_get_jukebox_invoice_check(
    pay_hash: str = Query(None),
    juke_id: str = Query(None),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No jukebox",
        )
    try:
        status = await check_invoice_status(jukebox.wallet, pay_hash)
        is_paid = not status.pending
    except:
        return {"paid": False}
    if is_paid:
        wallet = await get_wallet(jukebox.wallet)
        payment = await wallet.get_payment(pay_hash)
        await payment.set_pending(False)
        await update_jukebox_payment(pay_hash, paid=True)
        return {"paid": True}
    return {"paid": False}


@jukebox_ext.get("/api/v1/jukebox/jb/invoicep/{song_id}/{juke_id}/{pay_hash}")
async def api_get_jukebox_invoice_paid(
    song_id: str = Query(None),
    juke_id: str = Query(None),
    pay_hash: str = Query(None),
    retry: bool = Query(False),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No jukebox",
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
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Invoice not paid",
                            )
                        elif retry:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Failed to get auth",
                            )
                        else:
                            return api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash, retry=True
                            )
                    else:
                        raise HTTPException(
                            status_code=HTTPStatus.FORBIDDEN,
                            detail="Invoice not paid",
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
                        return jukebox_payment

                    elif r.status_code == 401 or r.status_code == 403:
                        token = await api_get_token(juke_id)
                        if token == False:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Invoice not paid",
                            )
                        elif retry:
                            raise HTTPException(
                                status_code=HTTPStatus.FORBIDDEN,
                                detail="Failed to get auth",
                            )
                        else:
                            return await api_get_jukebox_invoice_paid(
                                song_id, juke_id, pay_hash
                            )
                    else:
                        raise HTTPException(
                            status_code=HTTPStatus.OK,
                            detail="Invoice not paid",
                        )
            elif r.status_code == 401 or r.status_code == 403:
                token = await api_get_token(juke_id)
                if token == False:
                    raise HTTPException(
                        status_code=HTTPStatus.OK,
                        detail="Invoice not paid",
                    )
                elif retry:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail="Failed to get auth",
                    )
                else:
                    return await api_get_jukebox_invoice_paid(
                        song_id, juke_id, pay_hash
                    )
    raise HTTPException(
        status_code=HTTPStatus.OK,
        detail="Invoice not paid",
    )


############################GET TRACKS


@jukebox_ext.get("/api/v1/jukebox/jb/currently/{juke_id}")
async def api_get_jukebox_currently(
    retry: bool = Query(False),
    juke_id: str = Query(None),
):
    try:
        jukebox = await get_jukebox(juke_id)
    except:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="No jukebox",
        )
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                "https://api.spotify.com/v1/me/player/currently-playing?market=ES",
                timeout=40,
                headers={"Authorization": "Bearer " + jukebox.sp_access_token},
            )
            if r.status_code == 204:
                raise HTTPException(
                    status_code=HTTPStatus.OK,
                    detail="Nothing",
                )
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
                    return track
                except:
                    raise HTTPException(
                        status_code=HTTPStatus.NOT_FOUND,
                        detail="Something went wrong",
                    )

            elif r.status_code == 401:
                token = await api_get_token(juke_id)
                if token == False:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail="INvoice not paid",
                    )
                elif retry:
                    raise HTTPException(
                        status_code=HTTPStatus.FORBIDDEN,
                        detail="Failed to get auth",
                    )
                else:
                    return await api_get_jukebox_currently(retry=True, juke_id=juke_id)
            else:
                raise HTTPException(
                    status_code=HTTPStatus.NOT_FOUND,
                    detail="Something went wrong",
                )
        except:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Something went wrong",
            )
