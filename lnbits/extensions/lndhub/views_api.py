import time
from base64 import urlsafe_b64encode
from pydantic import BaseModel

from lnbits.core.services import pay_invoice, create_invoice
from lnbits.core.crud import get_payments, delete_expired_invoices
from lnbits.decorators import api_validate_post_request, WalletTypeInfo, get_key_type
from lnbits.settings import WALLET
from lnbits import bolt11

from . import lndhub_ext
from .decorators import check_wallet
from .utils import to_buffer, decoded_as_lndhub
from http import HTTPStatus
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse, JSONResponse  # type: ignore
from fastapi.params import Depends
from fastapi.param_functions import Query
from fastapi.security import OAuth2PasswordBearer


@lndhub_ext.get("/ext/getinfo")
async def lndhub_getinfo():
    raise HTTPException(
        status_code=HTTPStatus.UNAUTHORIZED,
        detail="bad auth",
    )

class AuthData(BaseModel):
    login: str = Query(None)
    password: str = Query(None)
    refresh_token: str = Query(None)


@lndhub_ext.post("/ext/auth")
async def lndhub_auth(
    data: AuthData
):
    token = (
        data.refresh_token
        if data.refresh_token
        else urlsafe_b64encode((data.login + ":" + data.password).encode("utf-8")).decode("ascii")
    )
    return {"refresh_token": token, "access_token": token}

class AddInvoice(BaseModel):
    amt: str = Query(None)
    memo: str = Query(None)
    preimage: str = Query(None)


@lndhub_ext.post("/ext/addinvoice")
async def lndhub_addinvoice(
    data: AddInvoice,
    wallet: WalletTypeInfo = Depends(get_key_type)
):
    try:
        _, pr = await create_invoice(
            wallet_id=wallet.wallet.id,
            amount=int(data.amt),
            memo=data.memo,
            extra={"tag": "lndhub"},
        )
    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Failed to create invoice",
        )

    invoice = bolt11.decode(pr)
    return {
        "pay_req": pr,
        "payment_request": pr,
        "add_index": "500",
        "r_hash": to_buffer(invoice.payment_hash),
        "hash": invoice.payment_hash,
    }


@lndhub_ext.post("/ext/payinvoice")
async def lndhub_payinvoice(
    wallet: WalletTypeInfo = Depends(get_key_type), invoice: str = Query(None)
):
    try:
        await pay_invoice(
            wallet_id=wallet.wallet.id,
            payment_request=invoice,
            extra={"tag": "lndhub"},
        )
    except:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="FPayment failed",
        )

    invoice: bolt11.Invoice = bolt11.decode(invoice)
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
# @check_wallet()
async def lndhub_balance(
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    return {"BTC": {"AvailableBalance": wallet.wallet.balance}}


@lndhub_ext.get("/ext/gettxs")
# @check_wallet()
async def lndhub_gettxs(
    wallet: WalletTypeInfo = Depends(get_key_type), limit: int = Query(0, ge=0, lt=200)
):
    print("WALLET", wallet)
    for payment in await get_payments(
        wallet_id=wallet.wallet.id,
        complete=False,
        pending=True,
        outgoing=True,
        incoming=False,
        exclude_uncheckable=True,
    ):
        await payment.set_pending(
            (await WALLET.get_payment_status(payment.checking_id)).pending
        )
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
                )
            )[:limit]
        )
    ]


@lndhub_ext.get("/ext/getuserinvoices")
async def lndhub_getuserinvoices(
    wallet: WalletTypeInfo = Depends(get_key_type), limit: int = Query(0, ge=0, lt=200)
):
    await delete_expired_invoices()
    for invoice in await get_payments(
        wallet_id=wallet.wallet.id,
        complete=False,
        pending=True,
        outgoing=False,
        incoming=True,
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
                )
            )[:limit]
        )
    ]


@lndhub_ext.get("/ext/getbtc")
async def lndhub_getbtc(wallet: WalletTypeInfo = Depends(get_key_type)):
    "load an address for incoming onchain btc"
    return []


@lndhub_ext.get("/ext/getpending")
# @check_wallet()
async def lndhub_getpending():
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
