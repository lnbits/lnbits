from quart import g, jsonify, request
from http import HTTPStatus

from lnbits.core.crud import get_user, get_wallet
from lnbits.core.services import create_invoice, check_invoice_status
from lnbits.decorators import api_check_wallet_key, api_validate_post_request

from . import paywall_ext
from .crud import create_paywall, get_paywall, get_paywalls, delete_paywall
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder

@paywall_ext.get("/api/v1/paywalls")
@api_check_wallet_key("invoice")
async def api_paywalls():
    wallet_ids = [g.wallet.id]

    if "all_wallets" in request.args:
        wallet_ids = (await get_user(g.wallet.user)).wallet_ids

    return (
        jsonable_encoder([paywall._asdict() for paywall in await get_paywalls(wallet_ids)]),
        HTTPStatus.OK,
    )


class CreateData(BaseModel):
    url:  Optional[str] = Query(...),
    memo:  Optional[str] = Query(...),
    description:  str = Query(None),
    amount:  int = Query(None),
    remembers:  bool = Query(None) 

@paywall_ext.post("/api/v1/paywalls")
@api_check_wallet_key("invoice")
async def api_paywall_create(data: CreateData):
    paywall = await create_paywall(wallet_id=g.wallet.id, **data)
    return paywall, HTTPStatus.CREATED


@paywall_ext.delete("/api/v1/paywalls/<paywall_id>")
@api_check_wallet_key("invoice")
async def api_paywall_delete(paywall_id):
    paywall = await get_paywall(paywall_id)

    if not paywall:
        return jsonable_encoder({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    if paywall.wallet != g.wallet.id:
        return jsonable_encoder({"message": "Not your paywall."}), HTTPStatus.FORBIDDEN

    await delete_paywall(paywall_id)

    return "", HTTPStatus.NO_CONTENT


@paywall_ext.post("/api/v1/paywalls/<paywall_id>/invoice")
async def api_paywall_create_invoice(amount: int = Query(..., ge=1), paywall_id = None):
    paywall = await get_paywall(paywall_id)

    if amount < paywall.amount:
        return (
            jsonable_encoder({"message": f"Minimum amount is {paywall.amount} sat."}),
            HTTPStatus.BAD_REQUEST,
        )

    try:
        amount = (
            amount if amount > paywall.amount else paywall.amount
        )
        payment_hash, payment_request = await create_invoice(
            wallet_id=paywall.wallet,
            amount=amount,
            memo=f"{paywall.memo}",
            extra={"tag": "paywall"},
        )
    except Exception as e:
        return jsonable_encoder({"message": str(e)}), HTTPStatus.INTERNAL_SERVER_ERROR

    return (
        jsonable_encoder({"payment_hash": payment_hash, "payment_request": payment_request}),
        HTTPStatus.CREATED,
    )


@paywall_ext.post("/api/v1/paywalls/<paywall_id>/check_invoice")
async def api_paywal_check_invoice(payment_hash: str = Query(...), paywall_id = None):
    paywall = await get_paywall(paywall_id)

    if not paywall:
        return jsonable_encoder({"message": "Paywall does not exist."}), HTTPStatus.NOT_FOUND

    try:
        status = await check_invoice_status(paywall.wallet, payment_hash)
        is_paid = not status.pending
    except Exception:
        return jsonable_encoder({"paid": False}), HTTPStatus.OK

    if is_paid:
        wallet = await get_wallet(paywall.wallet)
        payment = await wallet.get_payment(payment_hash)
        await payment.set_pending(False)

        return (
            jsonable_encoder({"paid": True, "url": paywall.url, "remembers": paywall.remembers}),
            HTTPStatus.OK,
        )

    return jsonable_encoder({"paid": False}), HTTPStatus.OK
