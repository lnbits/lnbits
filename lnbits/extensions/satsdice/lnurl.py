import shortuuid  # type: ignore
import hashlib
import math
from http import HTTPStatus
from datetime import datetime
from quart import jsonify, url_for, request
from lnbits.core.services import pay_invoice, create_invoice

from lnbits.utils.exchange_rates import get_fiat_rate_satoshis

from . import satsdice_ext
from .crud import (
    get_satsdice_withdraw_by_hash,
    update_satsdice_withdraw,
    get_satsdice_pay,
    create_satsdice_payment,
)
from lnurl import LnurlPayResponse, LnurlPayActionResponse, LnurlErrorResponse  # type: ignore


##############LNURLP STUFF


@satsdice_ext.route("/api/v1/lnurlp/<link_id>", methods=["GET"])
async def api_lnurlp_response(link_id):
    link = await get_satsdice_pay(link_id)
    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-payy not found."}),
            HTTPStatus.OK,
        )
    resp = LnurlPayResponse(
        callback=url_for(
            "satsdice.api_lnurlp_callback", link_id=link.id, _external=True
        ),
        min_sendable=math.ceil(link.min_bet * 1) * 1000,
        max_sendable=round(link.max_bet * 1) * 1000,
        metadata=link.lnurlpay_metadata,
    )
    params = resp.dict()

    return jsonify(params), HTTPStatus.OK


@satsdice_ext.route("/api/v1/lnurlp/cb/<link_id>", methods=["GET"])
async def api_lnurlp_callback(link_id):
    link = await get_satsdice_pay(link_id)
    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNUeL-pay not found."}),
            HTTPStatus.OK,
        )

    min, max = link.min_bet, link.max_bet
    min = link.min_bet * 1000
    max = link.max_bet * 1000

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

    payment_hash, payment_request = await create_invoice(
        wallet_id=link.wallet,
        amount=int(amount_received / 1000),
        memo="Satsdice bet",
        description_hash=hashlib.sha256(
            link.lnurlpay_metadata.encode("utf-8")
        ).digest(),
        extra={"tag": "satsdice", "link": link.id, "comment": "comment"},
    )

    success_action = link.success_action(payment_hash)
    link = await create_satsdice_payment(
        satsdice_pay=link.id, value=amount_received / 1000, payment_hash=payment_hash
    )
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


@satsdice_ext.route("/api/v1/lnurlw/<unique_hash>", methods=["GET"])
async def api_lnurlw_response(unique_hash):
    link = await get_satsdice_withdraw_by_hash(unique_hash)

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-satsdice not found."}),
            HTTPStatus.OK,
        )

    if link.used:
        return (
            jsonify({"status": "ERROR", "reason": "satsdice is spent."}),
            HTTPStatus.OK,
        )

    return jsonify(link.lnurl_response.dict()), HTTPStatus.OK


# CALLBACK


@satsdice_ext.route("/api/v1/lnurlw/cb/<unique_hash>", methods=["GET"])
async def api_lnurlw_callback(unique_hash):
    link = await get_satsdice_withdraw_by_hash(unique_hash)
    paylink = await get_satsdice_pay(link.satsdice_pay)
    k1 = request.args.get("k1", type=str)
    payment_request = request.args.get("pr", type=str)
    now = int(datetime.now().timestamp())

    if not link:
        return (
            jsonify({"status": "ERROR", "reason": "LNURL-satsdice not found."}),
            HTTPStatus.OK,
        )

    if link.used:
        return (
            jsonify({"status": "ERROR", "reason": "satsdice is spent."}),
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
        await update_satsdice_withdraw(link.id, used=1)

        await pay_invoice(
            wallet_id=paylink.wallet,
            payment_request=payment_request,
            max_sat=link.value,
            extra={"tag": "withdraw"},
        )

    except ValueError as e:
        await update_satsdice_withdraw(link.id, used=1)
        return jsonify({"status": "ERROR", "reason": str(e)})
    except PermissionError:
        await update_satsdice_withdraw(link.id, used=1)
        return jsonify({"status": "ERROR", "reason": "satsdice link is empty."})
    except Exception as e:
        await update_satsdice_withdraw(link.id, used=1)
        return jsonify({"status": "ERROR", "reason": str(e)})

    return jsonify({"status": "OK"}), HTTPStatus.OK
