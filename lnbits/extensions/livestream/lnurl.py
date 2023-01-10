import math
from http import HTTPStatus

from fastapi import HTTPException, Query, Request
from lnurl import LnurlErrorResponse, LnurlPayActionResponse, LnurlPayResponse
from lnurl.models import ClearnetUrl, LightningInvoice, MilliSatoshi

from lnbits.core.services import create_invoice

from . import livestream_ext
from .crud import get_livestream, get_livestream_by_track, get_track


@livestream_ext.get("/lnurl/{ls_id}", name="livestream.lnurl_livestream")
async def lnurl_livestream(ls_id, request: Request):
    ls = await get_livestream(ls_id)
    if not ls:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Livestream not found."
        )

    track = await get_track(ls.current_track)
    if not track:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="This livestream is offline."
        )

    resp = LnurlPayResponse(
        callback=ClearnetUrl(
            request.url_for("livestream.lnurl_callback", track_id=track.id),
            scheme="https",
        ),
        minSendable=MilliSatoshi(track.min_sendable),
        maxSendable=MilliSatoshi(track.max_sendable),
        metadata=await track.lnurlpay_metadata(),
    )

    params = resp.dict()
    params["commentAllowed"] = 300

    return params


@livestream_ext.get("/lnurl/t/{track_id}", name="livestream.lnurl_track")
async def lnurl_track(track_id, request: Request):
    track = await get_track(track_id)
    if not track:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Track not found.")

    resp = LnurlPayResponse(
        callback=ClearnetUrl(
            request.url_for("livestream.lnurl_callback", track_id=track.id),
            scheme="https",
        ),
        minSendable=MilliSatoshi(track.min_sendable),
        maxSendable=MilliSatoshi(track.max_sendable),
        metadata=await track.lnurlpay_metadata(),
    )

    params = resp.dict()
    params["commentAllowed"] = 300

    return params


@livestream_ext.get("/lnurl/cb/{track_id}", name="livestream.lnurl_callback")
async def lnurl_callback(
    track_id, request: Request, amount: int = Query(...), comment: str = Query("")
):
    track = await get_track(track_id)
    if not track:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Track not found.")

    amount_received = int(amount or 0)

    if amount_received < track.min_sendable:
        return LnurlErrorResponse(
            reason=f"Amount {round(amount_received / 1000)} is smaller than minimum {math.floor(track.min_sendable)}."
        ).dict()
    elif track.max_sendable < amount_received:
        return LnurlErrorResponse(
            reason=f"Amount {round(amount_received / 1000)} is greater than maximum {math.floor(track.max_sendable)}."
        ).dict()

    if len(comment or "") > 300:
        return LnurlErrorResponse(
            reason=f"Got a comment with {len(comment)} characters, but can only accept 300"
        ).dict()

    ls = await get_livestream_by_track(track_id)
    assert ls

    extra_amount = amount_received - int(amount_received * (100 - ls.fee_pct) / 100)

    payment_hash, payment_request = await create_invoice(
        wallet_id=ls.wallet,
        amount=int(amount_received / 1000),
        memo=await track.fullname(),
        unhashed_description=(await track.lnurlpay_metadata()).encode(),
        extra={
            "tag": "livestream",
            "track": track.id,
            "comment": comment,
            "amount": int(extra_amount / 1000),
        },
    )

    assert track.price_msat
    if amount_received < track.price_msat:
        success_action = None
    else:
        success_action = track.success_action(payment_hash, request=request)

    resp = LnurlPayActionResponse(
        pr=LightningInvoice(payment_request), successAction=success_action, routes=[]
    )

    return resp.dict()
