import time
from base64 import urlsafe_b64encode
from http import HTTPStatus

from fastapi import Depends, Query
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from lnbits import bolt11
from lnbits.core.crud import get_payments
from lnbits.core.services import create_invoice, pay_invoice
from lnbits.decorators import WalletTypeInfo
from lnbits.settings import get_wallet_class, settings

from . import lndhub_ext
from .decorators import check_wallet, require_admin_key
from .utils import decoded_as_lndhub, to_buffer


@lndhub_ext.get("/ext/getinfo")
async def lndhub_getinfo():
    return {"alias": settings.lnbits_site_title}


class AuthData(BaseModel):
    login: str = Query(None)
    password: str = Query(None)
    refresh_token: str = Query(None)


@lndhub_ext.post("/ext/auth")
async def lndhub_auth(data: AuthData):
    token = (
        data.refresh_token
        if data.refresh_token
        else urlsafe_b64encode((data.login + ":" + data.password).encode()).decode(
            "ascii"
        )
    )
    return {"refresh_token": token, "access_token": token}


class AddInvoice(BaseModel):
    amt: str = Query(...)
    memo: str = Query(...)
    preimage: str = Query(None)


@lndhub_ext.post("/ext/addinvoice")
async def lndhub_addinvoice(
    data: AddInvoice, wallet: WalletTypeInfo = Depends(check_wallet)
):
    try:
        _, pr = await create_invoice(
            wallet_id=wallet.wallet.id,
            amount=int(data.amt),
            memo=data.memo or settings.lnbits_site_title,
            extra={"tag": "lndhub"},
        )
    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Failed to create invoice"
        )
    invoice = bolt11.decode(pr)
    return {
        "pay_req": pr,
        "payment_request": pr,
        "add_index": "500",
        "r_hash": to_buffer(invoice.payment_hash),
        "hash": invoice.payment_hash,
    }


class CreateInvoice(BaseModel):
    invoice: str = Query(...)


@lndhub_ext.post("/ext/payinvoice")
async def lndhub_payinvoice(
    r_invoice: CreateInvoice, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    try:
        await pay_invoice(
            wallet_id=wallet.wallet.id,
            payment_request=r_invoice.invoice,
            extra={"tag": "lndhub"},
        )
    except:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Payment failed")

    invoice: bolt11.Invoice = bolt11.decode(r_invoice.invoice)

    return {
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
async def lndhub_balance(
    wallet: WalletTypeInfo = Depends(check_wallet),
):
    return {"BTC": {"AvailableBalance": wallet.wallet.balance}}


@lndhub_ext.get("/ext/gettxs")
async def lndhub_gettxs(
    wallet: WalletTypeInfo = Depends(check_wallet),
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0),
):
    for payment in await get_payments(
        wallet_id=wallet.wallet.id,
        complete=False,
        pending=True,
        outgoing=True,
        incoming=False,
        limit=limit,
        offset=offset,
        exclude_uncheckable=True,
    ):
        await payment.check_status()

    return [
        {
            "payment_preimage": payment.preimage,
            "payment_hash": payment.payment_hash,
            "fee_msat": payment.fee * 1000,
            "type": "paid_invoice",
            "fee": payment.fee,
            "value": int(payment.amount / 1000),
            "timestamp": payment.time,
            "memo": payment.memo if not payment.pending else "Payment in transition",
        }
        for payment in reversed(
            (
                await get_payments(
                    wallet_id=wallet.wallet.id,
                    pending=True,
                    complete=True,
                    outgoing=True,
                    incoming=False,
                    limit=limit,
                    offset=offset,
                )
            )
        )
    ]


@lndhub_ext.get("/ext/getuserinvoices")
async def lndhub_getuserinvoices(
    wallet: WalletTypeInfo = Depends(check_wallet),
    limit: int = Query(20, ge=1, le=20),
    offset: int = Query(0, ge=0),
):
    WALLET = get_wallet_class()
    for invoice in await get_payments(
        wallet_id=wallet.wallet.id,
        complete=False,
        pending=True,
        outgoing=False,
        incoming=True,
        limit=limit,
        offset=offset,
        exclude_uncheckable=True,
    ):
        await invoice.set_pending(
            (await WALLET.get_invoice_status(invoice.checking_id)).pending
        )

    return [
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
                    wallet_id=wallet.wallet.id,
                    pending=True,
                    complete=True,
                    incoming=True,
                    outgoing=False,
                    limit=limit,
                    offset=offset,
                )
            )
        )
    ]


@lndhub_ext.get("/ext/getbtc")
async def lndhub_getbtc(wallet: WalletTypeInfo = Depends(check_wallet)):
    "load an address for incoming onchain btc"
    return []


@lndhub_ext.get("/ext/getpending")
async def lndhub_getpending(wallet: WalletTypeInfo = Depends(check_wallet)):
    "pending onchain transactions"
    return []


@lndhub_ext.get("/ext/decodeinvoice")
async def lndhub_decodeinvoice(invoice: str = Query(None)):
    inv = bolt11.decode(invoice)
    return decoded_as_lndhub(inv)


@lndhub_ext.get("/ext/checkrouteinvoice")
async def lndhub_checkrouteinvoice():
    "not implemented on canonical lndhub"
    pass
