from http import HTTPStatus

from fastapi import Depends, HTTPException, Request
from lnurl.exceptions import InvalidUrl as LnurlInvalidUrl

from lnbits.decorators import WalletTypeInfo, get_key_type

from . import livestream_ext
from .crud import (
    add_producer,
    add_track,
    delete_track_from_livestream,
    get_or_create_livestream_by_wallet,
    get_producers,
    get_tracks,
    update_current_track,
    update_livestream_fee,
    update_track,
)
from .models import CreateTrack


@livestream_ext.get("/api/v1/livestream")
async def api_livestream_from_wallet(
    req: Request, g: WalletTypeInfo = Depends(get_key_type)
):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    assert ls
    tracks = await get_tracks(ls.id)
    producers = await get_producers(ls.id)

    try:
        return {
            **ls.dict(),
            **{
                "lnurl": ls.lnurl(request=req),
                "tracks": [
                    dict(lnurl=track.lnurl(request=req), **track.dict())
                    for track in tracks
                ],
                "producers": [producer.dict() for producer in producers],
            },
        }
    except LnurlInvalidUrl:
        raise HTTPException(
            status_code=HTTPStatus.UPGRADE_REQUIRED,
            detail="LNURLs need to be delivered over a publically accessible `https` domain or Tor.",
        )


@livestream_ext.put("/api/v1/livestream/track/{track_id}")
async def api_update_track(track_id, g: WalletTypeInfo = Depends(get_key_type)):
    try:
        id = int(track_id)
    except ValueError:
        id = 0

    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    assert ls
    await update_current_track(ls.id, None if id <= 0 else id)
    return "", HTTPStatus.NO_CONTENT


@livestream_ext.put("/api/v1/livestream/fee/{fee_pct}")
async def api_update_fee(fee_pct, g: WalletTypeInfo = Depends(get_key_type)):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    assert ls
    await update_livestream_fee(ls.id, int(fee_pct))
    return "", HTTPStatus.NO_CONTENT


@livestream_ext.post("/api/v1/livestream/tracks")
@livestream_ext.put("/api/v1/livestream/tracks/{id}")
async def api_add_track(
    data: CreateTrack, id=None, g: WalletTypeInfo = Depends(get_key_type)
):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    assert ls

    if data.producer_id:
        p_id = int(data.producer_id)
    elif data.producer_name:
        p_id = await add_producer(ls.id, data.producer_name)
    else:
        raise TypeError("need either producer_id or producer_name arguments")

    if id:
        await update_track(
            ls.id, id, data.name, data.download_url, data.price_msat or 0, p_id
        )
    else:
        await add_track(ls.id, data.name, data.download_url, data.price_msat or 0, p_id)
    return


@livestream_ext.delete("/api/v1/livestream/tracks/{track_id}")
async def api_delete_track(track_id, g: WalletTypeInfo = Depends(get_key_type)):
    ls = await get_or_create_livestream_by_wallet(g.wallet.id)
    assert ls
    await delete_track_from_livestream(ls.id, track_id)
    return "", HTTPStatus.NO_CONTENT
