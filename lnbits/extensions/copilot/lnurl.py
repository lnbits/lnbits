import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice

from . import copilot_ext
from .crud import get_copilot


@copilot_ext.route("/lnurl/<copilot_id>", methods=["GET"])
async def lnurl_response(copilot_id):
    copilot = await get_copilot(copilot_id)
    if not copilot:
        return jsonify({"status": "ERROR", "reason": "Copilot not found."})

    resp = LnurlPayResponse(
        callback=url_for(
            "copilot.lnurl_callback", _external=True
        ),
        min_sendable=copilot.amount,
        max_sendable=copilot.amount,
        metadata=copilot.lnurl_title,
    )

    params = resp.dict()
    params["commentAllowed"] = 300

    return jsonify(params)


@copilot_ext.route("/lnurl/cb", methods=["GET"])
async def lnurl_callback():

    amount_received = int(request.args.get("amount"))

    if amount_received < track.amount:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is smaller than minimum {math.floor(track.min_sendable)}."
                ).dict()
            ),
        )
    elif track.max_sendable < amount_received:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is greater than maximum {math.floor(track.max_sendable)}."
                ).dict()
            ),
        )

    comment = request.args.get("comment")
    if len(comment or "") > 300:
        return jsonify(
            LnurlErrorResponse(
                reason=f"Got a comment with {len(comment)} characters, but can only accept 300"
            ).dict()
        )

    copilot = await get_copilot_by_track(track_id)

    payment_hash, payment_request = await create_invoice(
        wallet_id=copilot.wallet,
        amount=int(amount_received / 1000),
        memo=await track.fullname(),
        description_hash=hashlib.sha256(
            (await track.lnurlpay_metadata()).encode("utf-8")
        ).digest(),
        extra={"tag": "copilot", "track": track.id, "comment": comment},
    )

    if amount_received < track.price_msat:
        success_action = None
    ecopilote:
        success_action = track.success_action(payment_hash)

    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=success_action,
        routes=[],
    )

    return jsonify(resp.dict())
