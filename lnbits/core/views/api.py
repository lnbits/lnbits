import asyncio
import hashlib
import json
from binascii import unhexlify
from http import HTTPStatus
from typing import Dict, List, Optional, Union
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

import httpx
from fastapi import Query, Request
from fastapi.exceptions import HTTPException
from fastapi.param_functions import Depends
from fastapi.params import Body
from pydantic import BaseModel
from pydantic.fields import Field
from sse_starlette.sse import EventSourceResponse

from lnbits import bolt11, lnurl
from lnbits.bolt11 import Invoice
from lnbits.core.models import Payment, Wallet
from lnbits.decorators import (
    WalletAdminKeyChecker,
    WalletInvoiceKeyChecker,
    WalletTypeInfo,
    get_key_type,
)
from lnbits.helpers import url_for
from lnbits.requestvars import g
from lnbits.utils.exchange_rates import (
    currencies,
    fiat_amount_as_satoshis,
    satoshis_amount_as_fiat,
)

from .. import core_app, db
from ..crud import (
    get_payments,
    get_standalone_payment,
    save_balance_check,
    update_wallet,
    create_payment,
    get_wallet,
    update_payment_status,
)
from ..services import (
    InvoiceFailure,
    PaymentFailure,
    check_invoice_status,
    create_invoice,
    pay_invoice,
    perform_lnurlauth,
)
from ..tasks import api_invoice_listeners
from lnbits.settings import LNBITS_ADMIN_USERS
from lnbits.helpers import urlsafe_short_hash


@core_app.get("/api/v1/wallet")
async def api_wallet(wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet_type == 0:
        return {
            "id": wallet.wallet.id,
            "name": wallet.wallet.name,
            "balance": wallet.wallet.balance_msat,
        }
    else:
        return {"name": wallet.wallet.name, "balance": wallet.wallet.balance_msat}


@core_app.put("/api/v1/wallet/balance/{amount}")
async def api_update_balance(
    amount: int, wallet: WalletTypeInfo = Depends(get_key_type)
):
    if not user.admin:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not an admin user"
        )

    payHash = urlsafe_short_hash()
    await create_payment(
        wallet_id=wallet.wallet.id,
        checking_id=payHash,
        payment_request="selfPay",
        payment_hash=payHash,
        amount=amount * 1000,
        memo="selfPay",
        fee=0,
    )
    await update_payment_status(checking_id=payHash, pending=False)
    updatedWallet = await get_wallet(wallet.wallet.id)

    return {
        "id": wallet.wallet.id,
        "name": wallet.wallet.name,
        "balance": amount,
    }


@core_app.put("/api/v1/wallet/{new_name}")
async def api_update_wallet(
    new_name: str, wallet: WalletTypeInfo = Depends(WalletAdminKeyChecker())
):
    await update_wallet(wallet.wallet.id, new_name)
    return {
        "id": wallet.wallet.id,
        "name": wallet.wallet.name,
        "balance": wallet.wallet.balance_msat,
    }


@core_app.get("/api/v1/payments")
async def api_payments(wallet: WalletTypeInfo = Depends(get_key_type)):
    await get_payments(wallet_id=wallet.wallet.id, pending=True, complete=True)
    pendingPayments = await get_payments(
        wallet_id=wallet.wallet.id, pending=True, exclude_uncheckable=True
    )
    for payment in pendingPayments:
        await check_invoice_status(
            wallet_id=payment.wallet_id, payment_hash=payment.payment_hash
        )
    return await get_payments(wallet_id=wallet.wallet.id, pending=True, complete=True)


class CreateInvoiceData(BaseModel):
    out: Optional[bool] = True
    amount: int = Query(None, ge=1)
    memo: str = None
    unit: Optional[str] = "sat"
    description_hash: Optional[str] = None
    lnurl_callback: Optional[str] = None
    lnurl_balance_check: Optional[str] = None
    extra: Optional[dict] = None
    webhook: Optional[str] = None
    bolt11: Optional[str] = None


async def api_payments_create_invoice(data: CreateInvoiceData, wallet: Wallet):
    if data.description_hash:
        description_hash = unhexlify(data.description_hash)
        memo = ""
    else:
        description_hash = b""
        memo = data.memo
    if data.unit == "sat":
        amount = data.amount
    else:
        price_in_sats = await fiat_amount_as_satoshis(data.amount, data.unit)
        amount = price_in_sats

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=wallet.id,
                amount=amount,
                memo=memo,
                description_hash=description_hash,
                extra=data.extra,
                webhook=data.webhook,
                conn=conn,
            )
        except InvoiceFailure as e:
            raise HTTPException(status_code=520, detail=str(e))
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if data.lnurl_callback:
        if "lnurl_balance_check" in data:
            save_balance_check(wallet.id, data.lnurl_balance_check)

        async with httpx.AsyncClient() as client:
            try:
                r = await client.get(
                    data.lnurl_callback,
                    params={
                        "pr": payment_request,
                        "balanceNotify": url_for(
                            f"/withdraw/notify/{urlparse(data.lnurl_callback).netloc}",
                            external=True,
                            wal=wallet.id,
                        ),
                    },
                    timeout=10,
                )
                if r.is_error:
                    lnurl_response = r.text
                else:
                    resp = json.loads(r.text)
                    if resp["status"] != "OK":
                        lnurl_response = resp["reason"]
                    else:
                        lnurl_response = True
            except (httpx.ConnectError, httpx.RequestError):
                lnurl_response = False

    return {
        "payment_hash": invoice.payment_hash,
        "payment_request": payment_request,
        # maintain backwards compatibility with API clients:
        "checking_id": invoice.payment_hash,
        "lnurl_response": lnurl_response,
    }


async def api_payments_pay_invoice(bolt11: str, wallet: Wallet):
    try:
        payment_hash = await pay_invoice(wallet_id=wallet.id, payment_request=bolt11)
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=str(e))
    except PaymentFailure as e:
        raise HTTPException(status_code=520, detail=str(e))
    except Exception as exc:
        raise exc

    return {
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }


@core_app.post(
    "/api/v1/payments",
    # deprecated=True,
    # description="DEPRECATED. Use /api/v2/TBD and /api/v2/TBD instead",
    status_code=HTTPStatus.CREATED,
)
async def api_payments_create(
    wallet: WalletTypeInfo = Depends(get_key_type),
    invoiceData: CreateInvoiceData = Body(...),
):
    if wallet.wallet_type < 0 or wallet.wallet_type > 2:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Key is invalid")

    if invoiceData.out is True and wallet.wallet_type == 0:
        if not invoiceData.bolt11:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="BOLT11 string is invalid or not given",
            )
        return await api_payments_pay_invoice(
            invoiceData.bolt11, wallet.wallet
        )  # admin key
    # invoice key
    return await api_payments_create_invoice(invoiceData, wallet.wallet)


class CreateLNURLData(BaseModel):
    description_hash: str
    callback: str
    amount: int
    comment: Optional[str] = None
    description: Optional[str] = None


@core_app.post("/api/v1/payments/lnurl")
async def api_payments_pay_lnurl(
    data: CreateLNURLData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    domain = urlparse(data.callback).netloc

    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(
                data.callback,
                params={"amount": data.amount, "comment": data.comment},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError
        except (httpx.ConnectError, httpx.RequestError):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Failed to connect to {domain}.",
            )

    params = json.loads(r.text)
    if params.get("status") == "ERROR":
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} said: '{params.get('reason', '')}'",
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != data.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} returned an invalid invoice. Expected {data.amount} msat, got {invoice.amount_msat}.",
        )

  #  if invoice.description_hash != data.description_hash:
  #      raise HTTPException(
  #          status_code=HTTPStatus.BAD_REQUEST,
  #          detail=f"{domain} returned an invalid invoice. Expected description_hash == {data.description_hash}, got {invoice.description_hash}.",
  #      )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if data.comment:
        extra["comment"] = data.comment

    payment_hash = await pay_invoice(
        wallet_id=wallet.wallet.id,
        payment_request=params["pr"],
        description=data.description,
        extra=extra,
    )

    return {
        "success_action": params.get("successAction"),
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }


async def subscribe(request: Request, wallet: Wallet):
    this_wallet_id = wallet.wallet.id

    payment_queue = asyncio.Queue(0)

    print("adding sse listener", payment_queue)
    api_invoice_listeners.append(payment_queue)

    send_queue = asyncio.Queue(0)

    async def payment_received() -> None:
        while True:
            payment: Payment = await payment_queue.get()
            if payment.wallet_id == this_wallet_id:
                await send_queue.put(("payment-received", payment))

    asyncio.create_task(payment_received())

    try:
        while True:
            typ, data = await send_queue.get()

            if data:
                jdata = json.dumps(dict(data.dict(), pending=False))

            # yield dict(id=1, event="this", data="1234")
            # await asyncio.sleep(2)
            yield dict(data=jdata, event=typ)
            # yield dict(data=jdata.encode("utf-8"), event=typ.encode("utf-8"))
    except asyncio.CancelledError:
        return


@core_app.get("/api/v1/payments/sse")
async def api_payments_sse(
    request: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    return EventSourceResponse(
        subscribe(request, wallet), ping=20, media_type="text/event-stream"
    )


@core_app.get("/api/v1/payments/{payment_hash}")
async def api_payment(payment_hash):
    payment = await get_standalone_payment(payment_hash)
    await check_invoice_status(payment.wallet_id, payment_hash)
    payment = await get_standalone_payment(payment_hash)
    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    elif not payment.pending:
        return {"paid": True, "preimage": payment.preimage}

    try:
        await payment.check_pending()
    except Exception:
        return {"paid": False}

    return {"paid": not payment.pending, "preimage": payment.preimage}


@core_app.get(
    "/api/v1/lnurlscan/{code}", dependencies=[Depends(WalletInvoiceKeyChecker())]
)
async def api_lnurlscan(code: str):
    try:
        url = lnurl.decode(code)
        domain = urlparse(url).netloc
    except:
        # parse internet identifier (user@domain.com)
        name_domain = code.split("@")
        if len(name_domain) == 2 and len(name_domain[1].split(".")) == 2:
            name, domain = name_domain
            url = (
                ("http://" if domain.endswith(".onion") else "https://")
                + domain
                + "/.well-known/lnurlp/"
                + name
            )
            # will proceed with these values
        else:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="invalid lnurl"
            )

    # params is what will be returned to the client
    params: Dict = {"domain": domain}

    if "tag=login" in url:
        params.update(kind="auth")
        params.update(callback=url)  # with k1 already in it

        lnurlauth_key = g().wallet.lnurlauth_key(domain)
        params.update(pubkey=lnurlauth_key.verifying_key.to_string("compressed").hex())
    else:
        async with httpx.AsyncClient() as client:
            r = await client.get(url, timeout=5)
            if r.is_error:
                raise HTTPException(
                    status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                    detail={"domain": domain, "message": "failed to get parameters"},
                )

        try:
            data = json.loads(r.text)
        except json.decoder.JSONDecodeError:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail={
                    "domain": domain,
                    "message": f"got invalid response '{r.text[:200]}'",
                },
            )

        try:
            tag = data["tag"]
            if tag == "channelRequest":
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail={
                        "domain": domain,
                        "kind": "channel",
                        "message": "unsupported",
                    },
                )

            params.update(**data)

            if tag == "withdrawRequest":
                params.update(kind="withdraw")
                params.update(fixed=data["minWithdrawable"] == data["maxWithdrawable"])

                # callback with k1 already in it
                parsed_callback: ParseResult = urlparse(data["callback"])
                qs: Dict = parse_qs(parsed_callback.query)
                qs["k1"] = data["k1"]

                # balanceCheck/balanceNotify
                if "balanceCheck" in data:
                    params.update(balanceCheck=data["balanceCheck"])

                # format callback url and send to client
                parsed_callback = parsed_callback._replace(
                    query=urlencode(qs, doseq=True)
                )
                params.update(callback=urlunparse(parsed_callback))

            if tag == "payRequest":
                params.update(kind="pay")
                params.update(fixed=data["minSendable"] == data["maxSendable"])

                params.update(
                    description_hash=hashlib.sha256(
                        data["metadata"].encode("utf-8")
                    ).hexdigest()
                )
                metadata = json.loads(data["metadata"])
                for [k, v] in metadata:
                    if k == "text/plain":
                        params.update(description=v)
                    if k == "image/jpeg;base64" or k == "image/png;base64":
                        data_uri = "data:" + k + "," + v
                        params.update(image=data_uri)
                    if k == "text/email" or k == "text/identifier":
                        params.update(targetUser=v)

                params.update(commentAllowed=data.get("commentAllowed", 0))
        except KeyError as exc:
            raise HTTPException(
                status_code=HTTPStatus.SERVICE_UNAVAILABLE,
                detail={
                    "domain": domain,
                    "message": f"lnurl JSON response invalid: {exc}",
                },
            )

    return params


@core_app.post("/api/v1/payments/decode")
async def api_payments_decode(data: str = Query(None)):
    try:
        if data["data"][:5] == "LNURL":
            url = lnurl.decode(data["data"])
            return {"domain": url}
        else:
            invoice = bolt11.decode(data["data"])
            return {
                "payment_hash": invoice.payment_hash,
                "amount_msat": invoice.amount_msat,
                "description": invoice.description,
                "description_hash": invoice.description_hash,
                "payee": invoice.payee,
                "date": invoice.date,
                "expiry": invoice.expiry,
                "secret": invoice.secret,
                "route_hints": invoice.route_hints,
                "min_final_cltv_expiry": invoice.min_final_cltv_expiry,
            }
    except:
        return {"message": "Failed to decode"}


@core_app.post("/api/v1/lnurlauth", dependencies=[Depends(WalletAdminKeyChecker())])
async def api_perform_lnurlauth(callback: str):
    err = await perform_lnurlauth(callback)
    if err:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail=err.reason
        )

    return ""


@core_app.get("/api/v1/currencies")
async def api_list_currencies_available():
    return list(currencies.keys())


class ConversionData(BaseModel):
    from_: str = Field("sat", alias="from")
    amount: float
    to: str = Query("usd")


@core_app.post("/api/v1/conversion")
async def api_fiat_as_sats(data: ConversionData):
    output = {}
    if data.from_ == "sat":
        output["sats"] = int(data.amount)
        output["BTC"] = data.amount / 100000000
        for currency in data.to.split(","):
            output[currency.strip().upper()] = await satoshis_amount_as_fiat(
                data.amount, currency.strip()
            )
        return output
    else:
        output[data.from_.upper()] = data.amount
        output["sats"] = await fiat_amount_as_satoshis(data.amount, data.to)
        output["BTC"] = output["sats"] / 100000000
        return output
