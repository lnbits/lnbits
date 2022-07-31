import hashlib
import math
from http import HTTPStatus
from os import name

from fastapi.exceptions import HTTPException
from fastapi.params import Query
from lnurl import LnurlErrorResponse, LnurlPayActionResponse, LnurlPayResponse
from starlette.requests import Request  # type: ignore

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
        callback=request.url_for("livestream.lnurl_callback", track_id=track.id),
        min_sendable=track.min_sendable,
        max_sendable=track.max_sendable,
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
        callback=request.url_for("livestream.lnurl_callback", track_id=track.id),
        min_sendable=track.min_sendable,
        max_sendable=track.max_sendable,
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

    payment_hash, payment_request = await create_invoice(
        wallet_id=ls.wallet,
        amount=int(amount_received / 1000),
        memo=await track.fullname(),
        description_hash=(await track.lnurlpay_metadata()).encode("utf-8"),
        extra={"tag": "livestream", "track": track.id, "comment": comment},
    )

    if amount_received < track.price_msat:
        success_action = None
    else:
        success_action = track.success_action(payment_hash, request=request)

    resp = LnurlPayActionResponse(
        pr=payment_request, success_action=success_action, routes=[]
    )

    return resp.dict()
