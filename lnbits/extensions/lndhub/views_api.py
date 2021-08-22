import time
from base64 import urlsafe_b64encode
from quart import jsonify, g, request

from fastapi import FastAPI, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lnbits.core.services import pay_invoice, create_invoice
from lnbits.core.crud import get_payments, delete_expired_invoices
from lnbits.decorators import api_validate_post_request
from lnbits.settings import WALLET
from lnbits import bolt11

from . import lndhub_ext
from .decorators import check_wallet
from .utils import to_buffer, decoded_as_lndhub


@lndhub_ext.get("/ext/getinfo")
async def lndhub_getinfo():
    return {"error": True, "code": 1, "message": "bad auth"}


@lndhub_ext.post("/ext/auth")
# @api_validate_post_request(
#     schema={
#         "login": {"type": "string", "required": True, "excludes": "refresh_token"},
#         "password": {"type": "string", "required": True, "excludes": "refresh_token"},
#         "refresh_token": {
#             "type": "string",
#             "required": True,
#             "excludes": ["login", "password"],
#         },
#     }
# )
async def lndhub_auth(login: str, password: str, refresh_token: str): #missing the "excludes" thing
    token = (
        refresh_token
        if refresh_token
        else urlsafe_b64encode(
            (login + ":" + password).encode("utf-8")
        ).decode("ascii")
    )
    return {"refresh_token": token, "access_token": token}


@lndhub_ext.post("/ext/addinvoice")
@check_wallet()
# @api_validate_post_request(
#     schema={
#         "amt": {"type": "string", "required": True},
#         "memo": {"type": "string", "required": True},
#         "preimage": {"type": "string", "required": False},
#     }
# )
async def lndhub_addinvoice(amt: str, memo: str, preimage: str = ""):
    try:
        _, pr = await create_invoice(
            wallet_id=g.wallet.id,
            amount=int(amt),
            memo=memo,
            extra={"tag": "lndhub"},
        )
    except Exception as e:
        return
            {
                "error": True,
                "code": 7,
                "message": "Failed to create invoice: " + str(e),
            }


    invoice = bolt11.decode(pr)
    return
        {
            "pay_req": pr,
            "payment_request": pr,
            "add_index": "500",
            "r_hash": to_buffer(invoice.payment_hash),
            "hash": invoice.payment_hash,
        }



@lndhub_ext.post("/ext/payinvoice")
@check_wallet(requires_admin=True)
# @api_validate_post_request(schema={"invoice": {"type": "string", "required": True}})
async def lndhub_payinvoice(invoice: str):
    try:
        await pay_invoice(
            wallet_id=g.wallet.id,
            payment_request=invoice,
            extra={"tag": "lndhub"},
        )
    except Exception as e:
        return
            {
                "error": True,
                "code": 10,
                "message": "Payment failed: " + str(e),
            }


    invoice: bolt11.Invoice = bolt11.decode(invoice)
    return
        {
            "payment_error": "",
            "payment_preimage": "0" * 64,
            "route": {},
            "payment_hash": invoice.payment_hash,
            "decoded": decoded_as_lndhub(invoice),
            "fee_msat": 0,
            "type": "paid_invoice",
            "fee": 0,
            "value": invoice.amount_msat / 1000,
            "timestamp": int(time.time()),
            "memo": invoice.description,
        }



@lndhub_ext.get("/ext/balance")
@check_wallet()
async def lndhub_balance():
    return {"BTC": {"AvailableBalance": g.wallet.balance}}


@lndhub_ext.get("/ext/gettxs")
@check_wallet()
async def lndhub_gettxs():
    for payment in await get_payments(
        wallet_id=g.wallet.id,
        complete=False,
        pending=True,
        outgoing=True,
        incoming=False,
        exclude_uncheckable=True,
    ):
        await payment.set_pending(
            (await WALLET.get_payment_status(payment.checking_id)).pending
        )

    limit = int(request.args.get("limit", 200))
    return
        [
            {
                "payment_preimage": payment.preimage,
                "payment_hash": payment.payment_hash,
                "fee_msat": payment.fee * 1000,
                "type": "paid_invoice",
                "fee": payment.fee,
                "value": int(payment.amount / 1000),
                "timestamp": payment.time,
                "memo": payment.memo
                if not payment.pending
                else "Payment in transition",
            }
            for payment in reversed(
                (
                    await get_payments(
                        wallet_id=g.wallet.id,
                        pending=True,
                        complete=True,
                        outgoing=True,
                        incoming=False,
                    )
                )[:limit]
            )
        ]



@lndhub_ext.get("/ext/getuserinvoices")
@check_wallet()
async def lndhub_getuserinvoices():
    await delete_expired_invoices()
    for invoice in await get_payments(
        wallet_id=g.wallet.id,
        complete=False,
        pending=True,
        outgoing=False,
        incoming=True,
        exclude_uncheckable=True,
    ):
        await invoice.set_pending(
            (await WALLET.get_invoice_status(invoice.checking_id)).pending
        )

    limit = int(request.args.get("limit", 200))
    return
        [
            {
                "r_hash": to_buffer(invoice.payment_hash),
                "payment_request": invoice.bolt11,
                "add_index": "500",
                "description": invoice.memo,
                "payment_hash": invoice.payment_hash,
                "ispaid": not invoice.pending,
                "amt": int(invoice.amount / 1000),
                "expire_time": int(time.time() + 1800),
                "timestamp": invoice.time,
                "type": "user_invoice",
            }
            for invoice in reversed(
                (
                    await get_payments(
                        wallet_id=g.wallet.id,
                        pending=True,
                        complete=True,
                        incoming=True,
                        outgoing=False,
                    )
                )[:limit]
            )
        ]



@lndhub_ext.get("/ext/getbtc")
@check_wallet()
async def lndhub_getbtc():
    "load an address for incoming onchain btc"
    return []


@lndhub_ext.get("/ext/getpending")
@check_wallet()
async def lndhub_getpending():
    "pending onchain transactions"
    return []


@lndhub_ext.get("/ext/decodeinvoice")
async def lndhub_decodeinvoice():
    invoice = request.args.get("invoice")
    inv = bolt11.decode(invoice)
    return decoded_as_lndhub(inv)


@lndhub_ext.get("/ext/checkrouteinvoice")
async def lndhub_checkrouteinvoice():
    "not implemented on canonical lndhub"
    pass
