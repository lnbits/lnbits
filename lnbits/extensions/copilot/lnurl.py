import json
import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice

from . import copilot_ext
from .crud import get_copilot


@copilot_ext.route("/lnurl/<cp_id>", methods=["GET"])
async def lnurl_response(cp_id):
    cp = await get_copilot(cp_id)
    if not cp:
        return jsonify({"status": "ERROR", "reason": "Copilot not found."})

    resp = LnurlPayResponse(
        callback=url_for("copilot.lnurl_callback", cp_id=cp_id, _external=True),
        min_sendable=10000,
        max_sendable=50000000,
        metadata=LnurlPayMetadata(json.dumps([["text/plain", str(cp.lnurl_title)]])),
    )

    params = resp.dict()
    if cp.show_message:
        params["commentAllowed"] = 300

    return jsonify(params)


@copilot_ext.route("/lnurl/cb/<cp_id>", methods=["GET"])
async def lnurl_callback(cp_id):
    cp = await get_copilot(cp_id)
    if not cp:
        return jsonify({"status": "ERROR", "reason": "Copilot not found."})

    amount_received = int(request.args.get("amount"))

    if amount_received < 10000:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is smaller than minimum 10 sats."
                ).dict()
            ),
        )
    elif amount_received / 1000 > 10000000:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is greater than maximum 50000."
                ).dict()
            ),
        )
    comment = ""
    if request.args.get("comment"):
        comment = request.args.get("comment")
        if len(comment or "") > 300:
            return jsonify(
                LnurlErrorResponse(
                    reason=f"Got a comment with {len(comment)} characters, but can only accept 300"
                ).dict()
            )
        if len(comment) < 1:
            comment = "none"

    payment_hash, payment_request = await create_invoice(
        wallet_id=cp.wallet,
        amount=int(amount_received / 1000),
        memo=cp.lnurl_title,
        description_hash=hashlib.sha256(
            (
                LnurlPayMetadata(json.dumps([["text/plain", str(cp.lnurl_title)]]))
            ).encode("utf-8")
        ).digest(),
        extra={"tag": "copilot", "copilot": cp.id, "comment": comment},
    )
    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=None,
        disposable=False,
        routes=[],
    )
    return jsonify(resp.dict())
