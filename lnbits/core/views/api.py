import asyncio
import binascii
import hashlib
import json
import os
import shutil
import time
import uuid
import zipfile
from http import HTTPStatus
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

import async_timeout
import httpx
import pyqrcode
from fastapi import Depends, Header, Query, Request
from fastapi.exceptions import HTTPException
from fastapi.params import Body
from genericpath import isfile
from loguru import logger
from pydantic import BaseModel
from pydantic.fields import Field
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from starlette.responses import HTMLResponse, StreamingResponse

from lnbits import bolt11, lnurl
from lnbits.core.helpers import (
    download_url,
    get_installable_extensions,
    migrate_extension_database,
)
from lnbits.core.models import Payment, User, Wallet
from lnbits.decorators import (
    WalletTypeInfo,
    check_user_exists,
    get_key_type,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import Extension, url_for, urlsafe_short_hash
from lnbits.settings import (
    LNBITS_ADMIN_USERS,
    LNBITS_DATA_FOLDER,
    LNBITS_SITE_TITLE,
    WALLET,
)
from lnbits.utils.exchange_rates import (
    currencies,
    fiat_amount_as_satoshis,
    satoshis_amount_as_fiat,
)

from .. import core_app, core_app_extra, db
from ..crud import (
    create_payment,
    get_dbversions,
    get_payments,
    get_standalone_payment,
    get_total_balance,
    get_wallet,
    get_wallet_for_key,
    save_balance_check,
    update_payment_status,
    update_wallet,
)
from ..services import (
    InvoiceFailure,
    PaymentFailure,
    check_transaction_status,
    create_invoice,
    pay_invoice,
    perform_lnurlauth,
)
from ..tasks import api_invoice_listeners


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
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
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
    new_name: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    await update_wallet(wallet.wallet.id, new_name)
    return {
        "id": wallet.wallet.id,
        "name": wallet.wallet.name,
        "balance": wallet.wallet.balance_msat,
    }


@core_app.get("/api/v1/payments")
async def api_payments(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    wallet: WalletTypeInfo = Depends(get_key_type),
):
    pendingPayments = await get_payments(
        wallet_id=wallet.wallet.id,
        pending=True,
        exclude_uncheckable=True,
        limit=limit,
        offset=offset,
    )
    for payment in pendingPayments:
        await check_transaction_status(
            wallet_id=payment.wallet_id, payment_hash=payment.payment_hash
        )
    return await get_payments(
        wallet_id=wallet.wallet.id,
        pending=True,
        complete=True,
        limit=limit,
        offset=offset,
    )


class CreateInvoiceData(BaseModel):
    out: Optional[bool] = True
    amount: float = Query(None, ge=0)
    memo: Optional[str] = None
    unit: Optional[str] = "sat"
    description_hash: Optional[str] = None
    unhashed_description: Optional[str] = None
    lnurl_callback: Optional[str] = None
    lnurl_balance_check: Optional[str] = None
    extra: Optional[dict] = None
    webhook: Optional[str] = None
    internal: Optional[bool] = False
    bolt11: Optional[str] = None


async def api_payments_create_invoice(data: CreateInvoiceData, wallet: Wallet):
    if data.description_hash:
        try:
            description_hash = binascii.unhexlify(data.description_hash)
        except binascii.Error:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="'description_hash' must be a valid hex string",
            )
        unhashed_description = b""
        memo = ""
    elif data.unhashed_description:
        try:
            unhashed_description = binascii.unhexlify(data.unhashed_description)
        except binascii.Error:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="'unhashed_description' must be a valid hex string",
            )
        description_hash = b""
        memo = ""
    else:
        description_hash = b""
        unhashed_description = b""
        memo = data.memo or LNBITS_SITE_TITLE
    if data.unit == "sat":
        amount = int(data.amount)
    else:
        assert data.unit is not None, "unit not set"
        price_in_sats = await fiat_amount_as_satoshis(data.amount, data.unit)
        amount = price_in_sats

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=wallet.id,
                amount=amount,
                memo=memo,
                description_hash=description_hash,
                unhashed_description=unhashed_description,
                extra=data.extra,
                webhook=data.webhook,
                internal=data.internal,
                conn=conn,
            )
        except InvoiceFailure as e:
            raise HTTPException(status_code=520, detail=str(e))
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if data.lnurl_callback:
        if data.lnurl_balance_check is not None:
            await save_balance_check(wallet.id, data.lnurl_balance_check)

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
    status_code=HTTPStatus.CREATED,
)
async def api_payments_create(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
    invoiceData: CreateInvoiceData = Body(...),  # type: ignore
):
    if invoiceData.out is True and wallet.wallet_type == 0:
        if not invoiceData.bolt11:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="BOLT11 string is invalid or not given",
            )
        return await api_payments_pay_invoice(
            invoiceData.bolt11, wallet.wallet
        )  # admin key
    elif not invoiceData.out:
        # invoice key
        return await api_payments_create_invoice(invoiceData, wallet.wallet)
    else:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )


class CreateLNURLData(BaseModel):
    description_hash: str
    callback: str
    amount: int
    comment: Optional[str] = None
    description: Optional[str] = None


@core_app.post("/api/v1/payments/lnurl")
async def api_payments_pay_lnurl(
    data: CreateLNURLData, wallet: WalletTypeInfo = Depends(require_admin_key)
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
                raise httpx.ConnectError("LNURL callback connection error")
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

    if not params.get("pr"):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} did not return a payment request.",
        )

    invoice = bolt11.decode(params["pr"])
    if invoice.amount_msat != data.amount:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} returned an invalid invoice. Expected {data.amount} msat, got {invoice.amount_msat}.",
        )

    if invoice.description_hash != data.description_hash:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{domain} returned an invalid invoice. Expected description_hash == {data.description_hash}, got {invoice.description_hash}.",
        )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if data.comment:
        extra["comment"] = data.comment
    assert data.description is not None, "description is required"
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


async def subscribe_wallet_invoices(request: Request, wallet: Wallet):
    """
    Subscribe to new invoices for a wallet. Can be wrapped in EventSourceResponse.
    Listenes invoming payments for a wallet and yields jsons with payment details.
    """
    this_wallet_id = wallet.id

    payment_queue: asyncio.Queue[Payment] = asyncio.Queue(0)

    uid = f"{this_wallet_id}_{str(uuid.uuid4())[:8]}"
    logger.debug(f"adding sse listener for wallet: {uid}")
    api_invoice_listeners[uid] = payment_queue

    send_queue: asyncio.Queue[Tuple[str, Payment]] = asyncio.Queue(0)

    async def payment_received() -> None:
        while True:
            try:
                async with async_timeout.timeout(1):
                    payment: Payment = await payment_queue.get()
                    if payment.wallet_id == this_wallet_id:
                        logger.debug("sse listener: payment receieved", payment)
                        await send_queue.put(("payment-received", payment))
            except asyncio.TimeoutError:
                pass

    task = asyncio.create_task(payment_received())

    try:
        while True:
            if await request.is_disconnected():
                await request.close()
                break
            typ, data = await send_queue.get()
            if data:
                jdata = json.dumps(dict(data.dict(), pending=False))

            yield dict(data=jdata, event=typ)
    except asyncio.CancelledError as e:
        logger.debug(f"CancelledError on listener {uid}: {e}")
        api_invoice_listeners.pop(uid)
        task.cancel()
        return


@core_app.get("/api/v1/payments/sse")
async def api_payments_sse(
    request: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    return EventSourceResponse(
        subscribe_wallet_invoices(request, wallet.wallet),
        ping=20,
        media_type="text/event-stream",
    )


@core_app.get("/api/v1/payments/{payment_hash}")
async def api_payment(payment_hash, X_Api_Key: Optional[str] = Header(None)):
    # We use X_Api_Key here because we want this call to work with and without keys
    # If a valid key is given, we also return the field "details", otherwise not
    wallet = await get_wallet_for_key(X_Api_Key) if type(X_Api_Key) == str else None

    # we have to specify the wallet id here, because postgres and sqlite return internal payments in different order
    # and get_standalone_payment otherwise just fetches the first one, causing unpredictable results
    payment = await get_standalone_payment(
        payment_hash, wallet_id=wallet.id if wallet else None
    )
    if payment is None:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    await check_transaction_status(payment.wallet_id, payment_hash)
    payment = await get_standalone_payment(
        payment_hash, wallet_id=wallet.id if wallet else None
    )
    if not payment:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Payment does not exist."
        )
    elif not payment.pending:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": True, "preimage": payment.preimage, "details": payment}
        return {"paid": True, "preimage": payment.preimage}

    try:
        await payment.check_status()
    except Exception:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": False, "details": payment}
        return {"paid": False}

    if wallet and wallet.id == payment.wallet_id:
        return {
            "paid": not payment.pending,
            "preimage": payment.preimage,
            "details": payment,
        }
    return {"paid": not payment.pending, "preimage": payment.preimage}


@core_app.get("/api/v1/lnurlscan/{code}")
async def api_lnurlscan(code: str, wallet: WalletTypeInfo = Depends(get_key_type)):
    try:
        url = lnurl.decode(code)
        domain = urlparse(url).netloc
    except:
        # parse internet identifier (user@domain.com)
        name_domain = code.split("@")
        if len(name_domain) == 2 and len(name_domain[1].split(".")) >= 2:
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

        lnurlauth_key = wallet.wallet.lnurlauth_key(domain)
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
            tag: str = data.get("tag")
            params.update(**data)
            if tag == "channelRequest":
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail={
                        "domain": domain,
                        "kind": "channel",
                        "message": "unsupported",
                    },
                )
            elif tag == "withdrawRequest":
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
            elif tag == "payRequest":
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


class DecodePayment(BaseModel):
    data: str


@core_app.post("/api/v1/payments/decode")
async def api_payments_decode(data: DecodePayment):
    payment_str = data.data
    try:
        if payment_str[:5] == "LNURL":
            url = lnurl.decode(payment_str)
            return {"domain": url}
        else:
            invoice = bolt11.decode(payment_str)
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


class Callback(BaseModel):
    callback: str = Query(...)


@core_app.post("/api/v1/lnurlauth")
async def api_perform_lnurlauth(
    callback: Callback, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    err = await perform_lnurlauth(callback.callback, wallet=wallet)
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
        output["BTC"] = data.amount / 100000000
        output["sats"] = int(data.amount)
        for currency in data.to.split(","):
            output[currency.strip().upper()] = await satoshis_amount_as_fiat(
                data.amount, currency.strip()
            )
        return output
    else:
        output[data.from_.upper()] = data.amount
        output["sats"] = await fiat_amount_as_satoshis(data.amount, data.from_)
        output["BTC"] = output["sats"] / 100000000
        return output


@core_app.get("/api/v1/qrcode/{data}", response_class=StreamingResponse)
async def img(request: Request, data):
    qr = pyqrcode.create(data)
    stream = BytesIO()
    qr.svg(stream, scale=3)
    stream.seek(0)

    async def _generator(stream: BytesIO):
        yield stream.getvalue()

    return StreamingResponse(
        _generator(stream),
        headers={
            "Content-Type": "image/svg+xml",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@core_app.get("/api/v1/audit/")
async def api_auditor(wallet: WalletTypeInfo = Depends(get_key_type)):
    if wallet.wallet.user not in LNBITS_ADMIN_USERS:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not an admin user"
        )

    total_balance = await get_total_balance()
    error_message, node_balance = await WALLET.status()

    if not error_message:
        delta = node_balance - total_balance
    else:
        node_balance, delta = None, None

    return {
        "node_balance_msats": node_balance,
        "lnbits_balance_msats": total_balance,
        "delta_msats": delta,
        "timestamp": int(time.time()),
    }


@core_app.post("/api/v1/extension/{ext_id}")
async def api_install_extension(ext_id: str, user: User = Depends(check_user_exists)):
    if not user.admin:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="Only for admin users"
        )

    try:
        extension_list: List[str] = await get_installable_extensions()
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cannot fetch installable extension list",
        )

    extension = [e for e in extension_list if e["id"] == ext_id][0]
    if not extension:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Unknown extension id: {ext_id}",
        )

    extensions_data_dir = os.path.join(LNBITS_DATA_FOLDER, "extensions")
    os.makedirs(extensions_data_dir, exist_ok=True)
    ext_data_dir = os.path.join(extensions_data_dir, ext_id)
    shutil.rmtree(ext_data_dir, True)
    ext_zip_file = os.path.join(extensions_data_dir, f"{ext_id}.zip")
    if os.path.isfile(ext_zip_file):
        os.remove(ext_zip_file)

    try:
        zip_file_url = extension["archive"]
        download_url(zip_file_url, ext_zip_file)
        with zipfile.ZipFile(ext_zip_file, "r") as zip_ref:
            zip_ref.extractall(extensions_data_dir)
    except Exception as ex:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Cannot fetch extension archvive file",
        )

    try:
        ext_dir = os.path.join("lnbits/extensions", ext_id)
        shutil.rmtree(ext_dir, True)
        shutil.copytree(ext_data_dir, ext_dir)

        # todo: is admin only
        ext = Extension(extension["id"], True, False, extension["name"])

        current_versions = await get_dbversions()
        current_version = current_versions.get(ext.code, 0)
        await migrate_extension_database(ext, current_version)

        register_new_ext_routes = getattr(core_app_extra, "register_new_ext_routes")
        register_new_ext_routes(ext)
    except Exception as ex:
        shutil.rmtree(ext_data_dir, True)
        shutil.rmtree(ext_dir, True)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(ex)
        )


@core_app.delete("/api/v1/extension/{ext_id}")
async def api_uninstall_extension(ext_id: str, user: User = Depends(check_user_exists)):
    if not user.admin:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED, detail="Only for admin users"
        )
    print("uninstall ", ext_id)
