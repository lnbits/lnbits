import shortuuid  # type: ignore
import hashlib
import math
from http import HTTPStatus
from datetime import datetime
from quart import jsonify, url_for, request
from lnbits.core.services import pay_invoice, create_invoice

from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import lnurlflip_ext
from .crud import (
    get_lnurlflip_withdraw_by_hash,
    update_lnurlflip_withdraw,
    increment_lnurlflip_pay,
)
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore



##############LNURLP STUFF


@lnurlflip_ext.route("/api/v1/lnurlp/<link_id>", methods=["GET"])
async def api_lnurlp_response(link_id):
    link = await increment_lnurlflip_pay(link_id, served_meta=1)
    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-pay not found."}),
            HTTPStatus.OK,
        )

    rate = await get_fiat_rate_satoshis(link.currency) if link.currency else 1
    resp = LnurlPayResponse(
        callback=url_for("lnurlp.api_lnurlp_callback", link_id=link.id, _external=True),
        min_sendable=math.ceil(link.min * rate) * 1000,
        max_sendable=round(link.max * rate) * 1000,
        metadata=link.lnurlpay_metadata,
    )
    params = resp.dict()

    if link.comment_chars > 0:
        params["commentAllowed"] = link.comment_chars

    return jsonify(params), HTTPStatus.OK


@lnurlflip_ext.route("/api/v1/lnurlp/cb/<link_id>", methods=["GET"])
async def api_lnurlp_callback(link_id):
    link = await increment_lnurlflip_pay(link_id, served_pr=1)
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
        extra={"tag": "lnurlflip", "link": link.id, "comment": comment},
    )

    success_action = link.success_action(payment_hash)
    if success_action:
        resp = LnurlPayActionResponse(
            pr=payment_request,
            success_action=success_action,
            routes=[],
        )
    else:
        resp = LnurlPayActionResponse(
            pr=payment_request,
            routes=[],
        )

    return jsonify(resp.dict()), HTTPStatus.OK

    
##############LNURLW STUFF


@lnurlflip_ext.route("/api/v1/lnurlw/<unique_hash>", methods=["GET"])
async def api_lnurlw_response(unique_hash):
    link = await get_lnurlflip_withdraw_by_hash(unique_hash)

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-lnurlflip not found."}),
            HTTPStatus.OK,
        )

    if link.is_spent:
        return (
            jsonify({"status": "ERROR", "reason": "lnurlflip is spent."}),
            HTTPStatus.OK,
        )

    return jsonify(link.lnurl_response.dict()), HTTPStatus.OK


# CALLBACK


@lnurlflip_ext.route("/api/v1/lnurlw/cb/<unique_hash>", methods=["GET"])
async def api_lnurlw_callback(unique_hash):
    link = await get_lnurlflip_withdraw_by_hash(unique_hash)
    k1 = request.args.get("k1", type=str)
    payment_request = request.args.get("pr", type=str)
    now = int(datetime.now().timestamp())

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-lnurlflip not found."}),
            HTTPStatus.OK,
        )

    if link.is_spent:
        return (
            jsonify({"status": "ERROR", "reason": "lnurlflip is spent."}),
            HTTPStatus.OK,
        )

    if link.k1 != k1:
        return jsonify({"status": "ERROR", "reason": "Bad request."}), HTTPStatus.OK

    if now < link.open_time:
        return (
            jsonify(
                {"status": "ERROR", "reason": f"Wait {link.open_time - now} seconds."}
            ),
            HTTPStatus.OK,
        )

    try:

        changesback = {"open_time": link.wait_time, "used": link.used}

        changes = {"open_time": link.wait_time + now, "used": link.used + 1}

        await update_lnurlflip_withdraw(link.id, **changes)

        await pay_invoice(
            wallet_id=link.wallet,
            payment_request=payment_request,
            max_sat=link.max_lnurlflipable,
            extra={"tag": "lnurlflip"},
        )
    except ValueError as e:
        await update_lnurlflip_withdraw(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": str(e)})
    except PermissionError:
        await update_lnurlflip_withdraw(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": "lnurlflip link is empty."})
    except Exception as e:
        await update_lnurlflip_withdraw(link.id, **changesback)
        return jsonify({"status": "ERROR", "reason": str(e)})

    return jsonify({"status": "OK"}), HTTPStatus.OK


