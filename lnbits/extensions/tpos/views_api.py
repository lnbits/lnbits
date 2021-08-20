from quart import g, jsonify, request
from http import HTTPStatus

from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import tpos_ext
from .crud import create_tpos, get_tpos, get_tposs, delete_tpos
from .models import TPoS


@tpos_ext.get("/api/v1/tposs")
@api_check_wallet_key("invoice")
async def api_tposs(all_wallets: boolean = Query(None)):
    wallet_ids = [g.wallet.id]
    if all_wallets:
         wallet_ids = wallet_ids = (await get_user(g.wallet.user)).wallet_ids(await get_user(g.wallet.user)).wallet_ids
    # if "all_wallets" in request.args:
    #     wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return [tpos._asdict() for tpos in await get_tposs(wallet_ids)], HTTPStatus.OK


@tpos_ext.post("/api/v1/tposs")
@api_check_wallet_key("invoice")
# @api_validate_post_request(
#     schema={
#         "name": {"type": "string", "empty": False, "required": True},
#         "currency": {"type": "string", "empty": False, "required": True},
#     }
# )
async def api_tpos_create(name: str = Query(...), currency: str = Query(...)):
    tpos = await create_tpos(wallet_id=g.wallet.id, **g.data)
    return tpos._asdict(), HTTPStatus.CREATED


@tpos_ext.delete("/api/v1/tposs/{tpos_id}")
@api_check_wallet_key("admin")
async def api_tpos_delete(tpos_id: str):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        return {"message": "TPoS does not exist."}, HTTPStatus.NOT_FOUND

    if tpos.wallet != g.wallet.id:
        return {"message": "Not your TPoS."}, HTTPStatus.FORBIDDEN

    await delete_tpos(tpos_id)

    return "", HTTPStatus.NO_CONTENT


@tpos_ext.post("/api/v1/tposs/{tpos_id}/invoices/")
# @api_validate_post_request(
#     schema={"amount": {"type": "integer", "min": 1, "required": True}}
# )
async def api_tpos_create_invoice(amount: int = Query(..., ge=1), tpos_id: str):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        return {"message": "TPoS does not exist."}, HTTPStatus.NOT_FOUND

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=tpos.wallet,
            amount=amount,
            memo=f"{tpos.name}",
            extra={"tag": "tpos"},
        )
    except Exception as e:
        return {"message": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR

    return {"payment_hash": payment_hash, "payment_request": payment_request}), HTTPStatus.CREATED


@tpos_ext.get("/api/v1/tposs/{tpos_id}/invoices/{payment_hash}")
async def api_tpos_check_invoice(tpos_id: str, payment_hash: str):
    tpos = await get_tpos(tpos_id)

    if not tpos:
        return {"message": "TPoS does not exist."}, HTTPStatus.NOT_FOUND

    try:
        status = await check_invoice_status(tpos.wallet, payment_hash)
        is_paid = not status.pending
    except Exception as exc:
        print(exc)
        return {"paid": False}, HTTPStatus.OK

    if is_paid:
        wallet = await get_wallet(tpos.wallet)
        payment = await wallet.get_payment(payment_hash)
        await payment.set_pending(False)

        return {"paid": True}, HTTPStatus.OK

    return {"paid": False}, HTTPStatus.OK
