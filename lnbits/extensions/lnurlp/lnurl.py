import hashlib
import math
from http import HTTPStatus
from quart import jsonify, url_for, request
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore

from lnbits.core.services import create_invoice
from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import lnurlp_ext
from .crud import increment_pay_link


@lnurlp_ext.route("/api/v1/lnurl/<link_id>", methods=["GET"])
async def api_lnurl_response(link_id):
    link = await increment_pay_link(link_id, served_meta=1)
    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}),
            HTTPStatus.OK,
        )

    rate = await get_fiat_rate_satoshis(link.currency) if link.currency else 1
    resp = LnurlPayResponse(
        callback=url_for("lnurlp.api_lnurl_callback", link_id=link.id, _external=True),
        min_sendable=math.ceil(link.min * rate) * 1000,
        max_sendable=round(link.max * rate) * 1000,
        metadata=link.lnurlpay_metadata,
    )
    params = resp.dict()

    if link.comment_chars > 0:
        params["commentAllowed"] = link.comment_chars

    return jsonify(params), HTTPStatus.OK


@lnurlp_ext.route("/api/v1/lnurl/cb/<link_id>", methods=["GET"])
async def api_lnurl_callback(link_id):
    link = await increment_pay_link(link_id, served_pr=1)
    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}),
            HTTPStatus.OK,
        )

    min, max = link.min, link.max
    rate = await get_fiat_rate_satoshis(link.currency) if link.currency else 1
    if link.currency:
        # allow some fluctuation (as the fiat price may have changed between the calls)
        min = rate * 995 * link.min
        max = rate * 1010 * link.max
    else:
        min = link.min * 1000
        max = link.max * 1000

    amount_received = int(request.args.get("amount") or 0)
    if amount_received < min:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {amount_received} is smaller than minimum {min}."
                ).dict()
            ),
            HTTPStatus.OK,
        )
    elif amount_received > max:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Amount {amount_received} is greater than maximum {max}."
                ).dict()
            ),
            HTTPStatus.OK,
        )

    comment = request.args.get("comment")
    if len(comment or "") > link.comment_chars:
        return (
            jsonify(
                LnurlErrorResponse(
                    reason=f"Got a comment with {len(comment)} characters, but can only accept {link.comment_chars}"
                ).dict()
            ),
            HTTPStatus.OK,
        )

    payment_hash, payment_request = await create_invoice(
        wallet_id=link.wallet,
        amount=int(amount_received / 1000),
        memo=link.description,
        description_hash=hashlib.sha256(
            link.lnurlpay_metadata.encode("utf-8")
        ).digest(),
        extra={"tag": "lnurlp", "link": link.id, "comment": comment},
    )

    resp = LnurlPayActionResponse(
        pr=payment_request,
        success_action=link.success_action(payment_hash),
        routes=[],
    )

    return jsonify(resp.dict()), HTTPStatus.OK
