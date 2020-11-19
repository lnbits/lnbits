import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice

from . import livestream_ext
from .crud import get_livestream, get_livestream_by_track, get_track


@livestream_ext.route("/lnurl/<ls_id>", methods=["GET"])
async def lnurl_response(ls_id):
    ls = await get_livestream(ls_id)
    if not ls:
        return jsonify({"status": "ERROR", "reason": "Livestream not found."})

    track = await get_track(ls.current_track)
    if not track:
        return jsonify({"status": "ERROR", "reason": "This livestream is offline."})

    resp = LnurlPayResponse(
        callback=url_for("livestream.lnurl_callback", track_id=track.id, _external=True),
        min_sendable=track.price_msat,
        max_sendable=track.price_msat * 5,
        metadata=await track.lnurlpay_metadata,
    )

    return jsonify(resp.dict())


@livestream_ext.route("/lnurl/cb/<track_id>", methods=["GET"])
async def lnurl_callback(track_id):
    track = await get_track(track_id)
    if not track:
        return jsonify({"status": "ERROR", "reason": "Couldn't find track."})

    amount_received = int(request.args.get("amount"))

    if amount_received < track.price_msat:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is smaller than minimum {math.floor(track.price_msat / 1000)}."
                ).dict()
            ),
        )
    elif track.price_msat * 5 < amount_received:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is greater than maximum {math.floor(track.price_msat * 5 / 1000)}."
                ).dict()
            ),
        )

    ls = await get_livestream_by_track(track_id)

    payment_hash, payment_request = await create_invoice(
        wallet_id=ls.wallet,
        amount=int(amount_received / 1000),
        memo=await track.description(),
        description_hash=hashlib.sha256((await track.lnurlpay_metadata).encode("utf-8")).digest(),
        extra={"tag": "livestream", "track": track.id},
    )

    resp = LnurlPayActionResponse(pr=payment_request, success_action=track.success_action(payment_hash), routes=[],)

    return jsonify(resp.dict())
