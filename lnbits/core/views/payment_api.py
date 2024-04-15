import asyncio
import json
import uuid
from http import HTTPStatus
from math import ceil
from typing import List, Optional, Union
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Request,
)
from fastapi.responses import JSONResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from lnbits import bolt11
from lnbits.core.db import db
from lnbits.core.models import (
    CreateInvoice,
    CreateLnurl,
    DecodePayment,
    Payment,
    PaymentFilters,
    PaymentHistoryPoint,
    Query,
    Wallet,
    WalletType,
)
from lnbits.db import Filters, Page
from lnbits.decorators import (
    WalletTypeInfo,
    get_key_type,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi, url_for
from lnbits.lnurl import decode as lnurl_decode
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from ..crud import (
    DateTrunc,
    get_payments,
    get_payments_history,
    get_payments_paginated,
    get_standalone_payment,
    get_wallet_for_key,
    save_balance_check,
    update_pending_payments,
)
from ..services import (
    InvoiceError,
    PaymentError,
    check_transaction_status,
    create_invoice,
    fee_reserve_total,
    pay_invoice,
)
from ..tasks import api_invoice_listeners

payment_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payment_router.get(
    "",
    name="Payment List",
    summary="get list of payments",
    response_description="list of payments",
    response_model=List[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments(
    wallet: WalletTypeInfo = Depends(get_key_type),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    return await get_payments(
        wallet_id=wallet.wallet.id,
        pending=True,
        complete=True,
        filters=filters,
    )


@payment_router.get(
    "/history",
    name="Get payments history",
    response_model=List[PaymentHistoryPoint],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_history(
    wallet: WalletTypeInfo = Depends(get_key_type),
    group: DateTrunc = Query("day"),
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    return await get_payments_history(wallet.wallet.id, group, filters)


@payment_router.get(
    "/paginated",
    name="Payment List",
    summary="get paginated list of payments",
    response_description="list of payments",
    response_model=Page[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_paginated(
    wallet: WalletTypeInfo = Depends(get_key_type),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(wallet.wallet.id)
    page = await get_payments_paginated(
        wallet_id=wallet.wallet.id,
        pending=True,
        complete=True,
        filters=filters,
    )
    return page


async def api_payments_create_invoice(data: CreateInvoice, wallet: Wallet):
    description_hash = b""
    unhashed_description = b""
    memo = data.memo or settings.lnbits_site_title
    if data.description_hash or data.unhashed_description:
        if data.description_hash:
            try:
                description_hash = bytes.fromhex(data.description_hash)
            except ValueError:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="'description_hash' must be a valid hex string",
                )
        if data.unhashed_description:
            try:
                unhashed_description = bytes.fromhex(data.unhashed_description)
            except ValueError:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="'unhashed_description' must be a valid hex string",
                )
        # do not save memo if description_hash or unhashed_description is set
        memo = ""

    async with db.connect() as conn:
        try:
            payment_hash, payment_request = await create_invoice(
                wallet_id=wallet.id,
                amount=data.amount,
                memo=memo,
                currency=data.unit,
                description_hash=description_hash,
                unhashed_description=unhashed_description,
                expiry=data.expiry,
                extra=data.extra,
                webhook=data.webhook,
                internal=data.internal,
                conn=conn,
            )
            # NOTE: we get the checking_id with a seperate query because create_invoice
            # does not return it and it would be a big hustle to change its return type
            # (used across extensions)
            payment_db = await get_standalone_payment(payment_hash, conn=conn)
            assert payment_db is not None, "payment not found"
            checking_id = payment_db.checking_id
        except InvoiceError as e:
            raise HTTPException(status_code=520, detail=str(e))
        except Exception as exc:
            raise exc

    invoice = bolt11.decode(payment_request)

    lnurl_response: Union[None, bool, str] = None
    if data.lnurl_callback:
        if data.lnurl_balance_check is not None:
            await save_balance_check(wallet.id, data.lnurl_balance_check)

        headers = {"User-Agent": settings.user_agent}
        async with httpx.AsyncClient(headers=headers) as client:
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
            except (httpx.ConnectError, httpx.RequestError) as ex:
                logger.error(ex)
                lnurl_response = False

    return {
        "payment_hash": invoice.payment_hash,
        "payment_request": payment_request,
        # maintain backwards compatibility with API clients:
        "checking_id": checking_id,
        "lnurl_response": lnurl_response,
    }


async def api_payments_pay_invoice(
    bolt11: str, wallet: Wallet, extra: Optional[dict] = None
):
    try:
        payment_hash = await pay_invoice(
            wallet_id=wallet.id, payment_request=bolt11, extra=extra
        )
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail=str(e))
    except PaymentError as e:
        raise HTTPException(status_code=520, detail=str(e))
    except Exception as exc:
        raise exc

    return {
        "payment_hash": payment_hash,
        # maintain backwards compatibility with API clients:
        "checking_id": payment_hash,
    }


@payment_router.post(
    "",
    summary="Create or pay an invoice",
    description="""
        This endpoint can be used both to generate and pay a BOLT11 invoice.
        To generate a new invoice for receiving funds into the authorized account,
        specify at least the first four fields in the POST body: `out: false`,
        `amount`, `unit`, and `memo`. To pay an arbitrary invoice from the funds
        already in the authorized account, specify `out: true` and use the `bolt11`
        field to supply the BOLT11 invoice to be paid.
    """,
    status_code=HTTPStatus.CREATED,
)
async def api_payments_create(
    wallet: WalletTypeInfo = Depends(require_invoice_key),
    invoice_data: CreateInvoice = Body(...),
):
    if invoice_data.out is True and wallet.wallet_type == WalletType.admin:
        if not invoice_data.bolt11:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="BOLT11 string is invalid or not given",
            )
        return await api_payments_pay_invoice(
            invoice_data.bolt11, wallet.wallet, invoice_data.extra
        )  # admin key
    elif not invoice_data.out:
        # invoice key
        return await api_payments_create_invoice(invoice_data, wallet.wallet)
    else:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            detail="Invoice (or Admin) key required.",
        )


@payment_router.get("/fee-reserve")
async def api_payments_fee_reserve(invoice: str = Query("invoice")) -> JSONResponse:
    invoice_obj = bolt11.decode(invoice)
    if invoice_obj.amount_msat:
        response = {
            "fee_reserve": fee_reserve_total(invoice_obj.amount_msat),
        }
        return JSONResponse(response)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Invoice has no amount.",
        )


@payment_router.post("/lnurl")
async def api_payments_pay_lnurl(
    data: CreateLnurl, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    domain = urlparse(data.callback).netloc

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        try:
            if data.unit and data.unit != "sat":
                amount_msat = await fiat_amount_as_satoshis(data.amount, data.unit)
                # no msat precision
                amount_msat = ceil(amount_msat // 1000) * 1000
            else:
                amount_msat = data.amount
            r = await client.get(
                data.callback,
                params={"amount": amount_msat, "comment": data.comment},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError("LNURL callback connection error")
            r.raise_for_status()
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
    if invoice.amount_msat != amount_msat:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                (
                    f"{domain} returned an invalid invoice. Expected"
                    f" {amount_msat} msat, got {invoice.amount_msat}."
                ),
            ),
        )

    extra = {}

    if params.get("successAction"):
        extra["success_action"] = params["successAction"]
    if data.comment:
        extra["comment"] = data.comment
    if data.unit and data.unit != "sat":
        extra["fiat_currency"] = data.unit
        extra["fiat_amount"] = data.amount / 1000
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

    try:
        while True:
            if await request.is_disconnected():
                await request.close()
                break
            payment: Payment = await payment_queue.get()
            if payment.wallet_id == this_wallet_id:
                logger.debug("sse listener: payment received", payment)
                yield {"data": payment.json(), "event": "payment-received"}
    except asyncio.CancelledError:
        logger.debug(f"removing listener for wallet {uid}")
    except Exception as exc:
        logger.error(f"Error in sse: {exc}")
    finally:
        api_invoice_listeners.pop(uid)


@payment_router.get("/sse")
async def api_payments_sse(
    request: Request, wallet: WalletTypeInfo = Depends(get_key_type)
):
    return EventSourceResponse(
        subscribe_wallet_invoices(request, wallet.wallet),
        ping=20,
        media_type="text/event-stream",
    )


# TODO: refactor this route into a public and admin one
@payment_router.get("/{payment_hash}")
async def api_payment(payment_hash, x_api_key: Optional[str] = Header(None)):
    # We use X_Api_Key here because we want this call to work with and without keys
    # If a valid key is given, we also return the field "details", otherwise not
    wallet = await get_wallet_for_key(x_api_key) if isinstance(x_api_key, str) else None

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


@payment_router.post("/decode", status_code=HTTPStatus.OK)
async def api_payments_decode(data: DecodePayment) -> JSONResponse:
    payment_str = data.data
    try:
        if payment_str[:5] == "LNURL":
            url = str(lnurl_decode(payment_str))
            return JSONResponse({"domain": url})
        else:
            invoice = bolt11.decode(payment_str)
            return JSONResponse(invoice.data)
    except Exception as exc:
        return JSONResponse(
            {"message": f"Failed to decode: {str(exc)}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )
