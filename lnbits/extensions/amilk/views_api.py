import httpx
from quart import g, jsonify, request, abort
from http import HTTPStatus
from lnurl import LnurlWithdrawResponse, handle as handle_lnurl  # type: ignore
from lnurl.exceptions import LnurlException  # type: ignore
from time import sleep

from lnbits.core.crud import get_user
from lnbits.decorators import api_check_wallet_key, api_validate_post_request
from lnbits.core.services import create_invoice, check_invoice_status

from . import amilk_ext
from .crud import create_amilk, get_amilk, get_amilks, delete_amilk


@amilk_ext.route("/api/v1/amilk", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_amilks():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([amilk._asdict() for amilk in await get_amilks(wallet_ids)]),
        HTTPStatus.OK,
    )


@amilk_ext.route("/api/v1/amilk/milk/<amilk_id>", methods=["GET"])
async def api_amilkit(amilk_id):
    milk = await get_amilk(amilk_id)
    memo = milk.id

    try:
        withdraw_res = handle_lnurl(milk.lnurl, response_class=LnurlWithdrawResponse)
    except LnurlException:
        abort(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    payment_hash, payment_request = await create_invoice(
        wallet_id=milk.wallet,
        amount=withdraw_res.max_sats,
        memo=memo,
        extra={"tag": "amilk"},
    )

    r = httpx.get(
        withdraw_res.callback.base,
        params={
            **withdraw_res.callback.query_params,
            **{"k1": withdraw_res.k1, "pr": payment_request},
        },
    )

    if r.is_error:
        abort(HTTPStatus.INTERNAL_SERVER_ERROR, "Could not process withdraw LNURL.")

    for i in range(10):
        sleep(i)
        invoice_status = await check_invoice_status(milk.wallet, payment_hash)
        if invoice_status.paid:
            return jsonify({"paid": True}), HTTPStatus.OK
        else:
            continue

    return jsonify({"paid": False}), HTTPStatus.OK


@amilk_ext.route("/api/v1/amilk", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "lnurl": {"type": "string", "empty": False, "required": True},
        "atime": {"type": "integer", "min": 0, "required": True},
        "amount": {"type": "integer", "min": 0, "required": True},
    }
)
async def api_amilk_create():
    amilk = await create_amilk(
        wallet_id=g.wallet.id,
        lnurl=g.data["lnurl"],
        atime=g.data["atime"],
        amount=g.data["amount"],
    )

    return jsonify(amilk._asdict()), HTTPStatus.CREATED


@amilk_ext.route("/api/v1/amilk/<amilk_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_amilk_delete(amilk_id):
    amilk = await get_amilk(amilk_id)

    if not amilk:
        return jsonify({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if amilk.wallet != g.wallet.id:
        return jsonify({"message": "Not your amilk."}), HTTPStatus.FORBIDDEN

    await delete_amilk(amilk_id)

    return "", HTTPStatus.NO_CONTENT
