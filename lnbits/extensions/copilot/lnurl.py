import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice

from . import copilot_ext
from .crud import get_copilot


@copilot_ext.route("/lnurl/<cp_id>", methods=["GET"])
async def lnurl_response(cp_id):
    cp = await get_copilot(cp_id)
    if not cp:
        return jsonify({"status": "ERROR", "reason": "Copilot not found."})

    resp = LnurlPayResponse(
        callback=url_for(
            "copilot.lnurl_callback", cp_id=cp_id, _external=True
        ),
        min_sendable=10,
        max_sendable=50000,
        metadata=cp.lnurl_title,
    )

    params = resp.dict()
    params["commentAllowed"] = 300

    return jsonify(params)


@copilot_ext.route("/lnurl/cb/<cp_id>", methods=["GET"])
async def lnurl_callback(cp_id):
    cp = await get_copilot(cp_id)
    if not cp:
        return jsonify({"status": "ERROR", "reason": "Copilot not found."})

    amount_received = int(request.args.get("amount"))

    if amount_received < 10:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is smaller than minimum 10 sats."
                ).dict()
            ),
        )
    elif 50000 > amount_received/1000:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is greater than maximum 50000."
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

    payment_hash, payment_request = await create_invoice(
        wallet_id=cp.wallet,
        amount=int(amount_received / 1000),
        memo=cp.lnurl_title,
        webhook="/copilot/api/v1/copilot/hook/" + cp_id,
        description_hash=hashlib.sha256(
            (cp.lnurl_title).encode("utf-8")
        ).digest(),
        extra={"tag": "copilot", "comment": comment},
    )

    if amount_received < track.price_msat:
        success_action = None
    else:
        success_action = track.success_action(payment_hash)

    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=success_action,
        routes=[],
    )
    
    return jsonify(resp.dict())