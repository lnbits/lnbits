import json
import hashlib
import math
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore
from lnurl.types import LnurlPayMetadata
from lnbits.core.services import create_invoice

from . import lnurlpos_ext
from .crud import get_lnurlpos


@lnurlpos_ext.route("/lnurl/<pos_id>/<amount_pin>", methods=["GET"])
async def lnurl_response(pos_id, amount_pin):
    pos = await get_lnurlpos(pos_id)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})
    #pos.secret decypt pin and amount bit
    decryptedPin = ""
    decryptedAmount = ""
    if type(decryptedAmount) != int or float:
        return jsonify({"status": "ERROR", "reason": "Incorrect amount."})
    resp = LnurlPayResponse(
        callback=url_for("lnurlpos.lnurl_callback", pos_id=pos_id, amount_pin=amount_pin, _external=True),
        min_sendable=int(decryptedAmount),
        max_sendable=int(decryptedAmount),
        metadata=LnurlPayMetadata(json.dumps([["text/plain", str(pos.lnurl_title)]])),
    )

    params = resp.dict()

    return jsonify(params)


@lnurlpos_ext.websocket("/ws/<id>/")
async def wss(id):
    lnurlpos = await get_lnurlpos(id)
    if not lnurlpos:
        return "", HTTPStatus.FORBIDDEN
    global connected_websockets
    send_channel, receive_channel = trio.open_memory_channel(0)
    connected_websockets[id].add(send_channel)
    try:
        while True:
            data = await receive_channel.receive()
            await websocket.send(data)
    finally:
        connected_websockets[id].remove(send_channel)


async def updater(lnurlpos_id, data, comment):
    lnurlpos = await get_lnurlpos(lnurlpos_id)
    if not lnurlpos:
        return
    for queue in connected_websockets[lnurlpos_id]:
        await queue.send(f"{data + '-' + comment}")
@lnurlpos_ext.route("/lnurl/cb/<pos_id>/<amount_pin>", methods=["GET"])
async def lnurl_callback(cp_id, amount_pin):
    pos = await get_lnurlpos(pos_id)
    if not pos:
        return jsonify({"status": "ERROR", "reason": "lnurlpos not found."})

    amount_received = int(request.args.get("amount"))
    #pos.secret decypt pin and amount bit
    decryptedPin = ""
    decryptedAmount = ""
    if amount_received != decryptedAmount:
        return jsonify({"status": "ERROR", "reason": "Incorrect amount."})

    if amount_received < 10000:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {round(amount_received / 1000)} is smaller than minimum 10 sats."
                ).dict()
            ),
        )

    payment_hash, payment_request = await create_invoice(
        wallet_id=pos.wallet,
        amount=int(amount_received / 1000),
        memo=pos.title,
        description_hash=hashlib.sha256(
            (
                LnurlPayMetadata(json.dumps([["text/plain", str(pos.title)]]))
            ).encode("utf-8")
        ).digest(),
        extra={"tag": "lnurlpos", "lnurlpos": pos.id, "lnurlpos_pay": amount_pin},
    )
    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=success_action,
        disposable=False,
        routes=[],
    )
    return jsonify(resp.dict())
