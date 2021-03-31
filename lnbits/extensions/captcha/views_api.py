from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import captcha_ext
from .crud import create_captcha, get_captcha, get_captchas, delete_captcha


@captcha_ext.route("/api/v1/captchas", methods=["GET"])
@api_check_wallet_key("invoice")
async def api_captchas():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonify([captcha._asdict() for captcha in await get_captchas(wallet_ids)]),
        HTTPStatus.OK,
    )


@captcha_ext.route("/api/v1/captchas", methods=["POST"])
@api_check_wallet_key("invoice")
@api_validate_post_request(
    schema={
        "url": {"type": "string", "empty": False, "required": True},
        "memo": {"type": "string", "empty": False, "required": True},
        "description": {
            "type": "string",
            "empty": True,
            "nullable": True,
            "required": False,
        },
        "amount": {"type": "integer", "min": 0, "required": True},
        "remembers": {"type": "boolean", "required": True},
    }
)
async def api_captcha_create():
    captcha = await create_captcha(wallet_id=g.wallet.id, **g.data)
    return jsonify(captcha._asdict()), HTTPStatus.CREATED


@captcha_ext.route("/api/v1/captchas/<captcha_id>", methods=["DELETE"])
@api_check_wallet_key("invoice")
async def api_captcha_delete(captcha_id):
    captcha = await get_captcha(captcha_id)

    if not captcha:
        return jsonify({"message": "captcha does not exist."}), HTTPStatus.NOT_FOUND

    if captcha.wallet != g.wallet.id:
        return jsonify({"message": "Not your captcha."}), HTTPStatus.FORBIDDEN

    await delete_captcha(captcha_id)

    return "", HTTPStatus.NO_CONTENT


@captcha_ext.route("/api/v1/captchas/<captcha_id>/invoice", methods=["POST"])
@api_validate_post_request(
    schema={"amount": {"type": "integer", "min": 1, "required": True}}
)
async def api_captcha_create_invoice(captcha_id):
    captcha = await get_captcha(captcha_id)

    if g.data["amount"] < captcha.amount:
        return (
            jsonify({"message": f"Minimum amount is {captcha.amount} sat."}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        amount = (
            g.data["amount"] if g.data["amount"] > captcha.amount else captcha.amount
        )
        payment_hash, payment_request = await create_invoice(
            wallet_id=captcha.wallet,
            amount=amount,
            memo=f"{captcha.memo}",
            extra={"tag": "captcha"},
        )
    except Exception as e:
        return jsonify({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return (
        jsonify({"payment_hash": payment_hash, "payment_request": payment_request}),
        HTTPStatus.CREATED,
    )


@captcha_ext.route("/api/v1/captchas/<captcha_id>/check_invoice", methods=["POST"])
@api_validate_post_request(
    schema={"payment_hash": {"type": "string", "empty": False, "required": True}}
)
async def api_paywal_check_invoice(captcha_id):
    captcha = await get_captcha(captcha_id)

    if not captcha:
        return jsonify({"message": "captcha does not exist."}), HTTPStatus.NOT_FOUND

    try:
        status = await check_invoice_status(captcha.wallet, g.data["payment_hash"])
        is_paid = not status.pending
    except Exception:
        return jsonify({"paid": False}), HTTPStatus.OK

    if is_paid:
        wallet = await get_wallet(captcha.wallet)
        payment = await wallet.get_payment(g.data["payment_hash"])
        await payment.set_pending(False)

        return (
            jsonify({"paid": True, "url": captcha.url, "remembers": captcha.remembers}),
            HTTPStatus.OK,
        )

    return jsonify({"paid": False}), HTTPStatus.OK
