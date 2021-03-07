import hashlib
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice

from . import offlineshop_ext
from .crud import get_shop, get_item
from .helpers import get_fiat_rate


@offlineshop_ext.route("/lnurl/<item_id>", methods=["GET"])
async def lnurl_response(item_id):
    item = await get_item(item_id)
    if not item:
        return jsonify({"status": "ERROR", "reason": "Item not found."})

    if not item.enabled:
        return jsonify({"status": "ERROR", "reason": "Item disabled."})

    rate = await get_fiat_rate(item.unit) if item.unit != "sat" else 1
    price_msat = item.price * 1000 * rate

    resp = LnurlPayResponse(
        callback=url_for("offlineshop.lnurl_callback", item_id=item.id, _external=True),
        min_sendable=price_msat,
        max_sendable=price_msat,
        metadata=await item.lnurlpay_metadata(),
    )

    return jsonify(resp.dict())


@offlineshop_ext.route("/lnurl/cb/<item_id>", methods=["GET"])
async def lnurl_callback(item_id):
    item = await get_item(item_id)
    if not item:
        return jsonify({"status": "ERROR", "reason": "Couldn't find item."})

    if item.unit == "sat":
        min = item.price * 1000
        max = item.price * 1000
    else:
        rate = await get_fiat_rate(item.unit)
        # allow some fluctuation (the fiat price may have changed between the calls)
        min = rate * 995 * item.price
        max = rate * 1010 * item.price

    amount_received = int(request.args.get("amount"))
    if amount_received < min:
        return jsonify(LnurlErrorResponse(reason=f"Amount {amount_received} is smaller than minimum {min}.").dict())
    elif amount_received > max:
        return jsonify(LnurlErrorResponse(reason=f"Amount {amount_received} is greater than maximum {max}.").dict())

    shop = await get_shop(item.shop)
    payment_hash, payment_request = await create_invoice(
        wallet_id=shop.wallet,
        amount=int(amount_received / 1000),
        memo=item.name,
        description_hash=hashlib.sha256((await item.lnurlpay_metadata()).encode("utf-8")).digest(),
        extra={"tag": "offlineshop", "item": item.id},
    )

    resp = LnurlPayActionResponse(pr=payment_request, success_action=item.success_action(shop, payment_hash), routes=[])

    return jsonify(resp.dict())
