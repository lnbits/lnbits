import json
import ssl
from http import HTTPStatus
from math import ceil
from typing import Optional
from urllib.parse import urlparse

import httpx
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse
from loguru import logger

from lnbits import bolt11
from lnbits.core.crud.payments import (
    get_payment_count_stats,
    get_wallets_stats,
)
from lnbits.core.models import (
    CreateInvoice,
    CreateLnurl,
    DecodePayment,
    KeyType,
    PayLnurlWData,
    Payment,
    PaymentCountField,
    PaymentCountStat,
    PaymentDailyStats,
    PaymentFilters,
    PaymentHistoryPoint,
    PaymentWalletStats,
)
from lnbits.core.models.users import User
from lnbits.db import Filters, Page
from lnbits.decorators import (
    WalletTypeInfo,
    check_user_exists,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import (
    check_callback_url,
    filter_dict_keys,
    generate_filter_params_openapi,
)
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
)
from ..services import (
    create_fiat_invoice,
    create_wallet_invoice,
    fee_reserve_total,
    get_payments_daily_stats,
    pay_invoice,
    update_pending_payment,
    update_pending_payments,
)

payment_router = APIRouter(prefix="/api/v1/payments", tags=["Payments"])


@payment_router.get(
    "",
    name="Payment List",
    summary="get list of payments",
    response_description="list of payments",
    response_model=list[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(key_info.wallet.id)
    return await get_payments(
        wallet_id=key_info.wallet.id,
        pending=True,
        complete=True,
        filters=filters,
    )


@payment_router.get(
    "/history",
    name="Get payments history",
    response_model=list[PaymentHistoryPoint],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_history(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
    group: DateTrunc = Query("day"),
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
):
    await update_pending_payments(key_info.wallet.id)
    return await get_payments_history(key_info.wallet.id, group, filters)


@payment_router.get(
    "/stats/count",
    name="Get payments history for all users",
    response_model=list[PaymentCountStat],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_counting_stats(
    count_by: PaymentCountField = Query("tag"),
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
    user: User = Depends(check_user_exists),
):

    if user.admin:
        # admin user can see payments from all wallets
        for_user_id = None
    else:
        # regular user can only see payments from their wallets
        for_user_id = user.id

    return await get_payment_count_stats(count_by, filters=filters, user_id=for_user_id)


@payment_router.get(
    "/stats/wallets",
    name="Get payments history for all users",
    response_model=list[PaymentWalletStats],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_wallets_stats(
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
    user: User = Depends(check_user_exists),
):

    if user.admin:
        # admin user can see payments from all wallets
        for_user_id = None
    else:
        # regular user can only see payments from their wallets
        for_user_id = user.id

    return await get_wallets_stats(filters, user_id=for_user_id)


@payment_router.get(
    "/stats/daily",
    name="Get payments history per day",
    response_model=list[PaymentDailyStats],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_daily_stats(
    user: User = Depends(check_user_exists),
    filters: Filters[PaymentFilters] = Depends(parse_filters(PaymentFilters)),
):

    if user.admin:
        # admin user can see payments from all wallets
        for_user_id = None
    else:
        # regular user can only see payments from their wallets
        for_user_id = user.id
    return await get_payments_daily_stats(filters, user_id=for_user_id)


@payment_router.get(
    "/paginated",
    name="Payment List",
    summary="get paginated list of payments",
    response_description="list of payments",
    response_model=Page[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_payments_paginated(
    key_info: WalletTypeInfo = Depends(require_invoice_key),
    filters: Filters = Depends(parse_filters(PaymentFilters)),
):
    page = await get_payments_paginated(
        wallet_id=key_info.wallet.id,
        filters=filters,
    )
    for payment in page.data:
        if payment.pending:
            await update_pending_payment(payment)

    return page


@payment_router.get(
    "/all/paginated",
    name="Payment List",
    summary="get paginated list of payments",
    response_description="list of payments",
    response_model=Page[Payment],
    openapi_extra=generate_filter_params_openapi(PaymentFilters),
)
async def api_all_payments_paginated(
    filters: Filters = Depends(parse_filters(PaymentFilters)),
    user: User = Depends(check_user_exists),
):
    if user.admin:
        # admin user can see payments from all wallets
        for_user_id = None
    else:
        # regular user can only see payments from their wallets
        for_user_id = user.id

    return await get_payments_paginated(
        filters=filters,
        user_id=for_user_id,
    )


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
    responses={
        400: {"description": "Invalid BOLT11 string or missing fields."},
        401: {"description": "Invoice (or Admin) key required."},
        520: {"description": "Payment or Invoice error."},
    },
)
async def api_payments_create(
    invoice_data: CreateInvoice,
    wallet: WalletTypeInfo = Depends(require_invoice_key),
) -> Payment:
    wallet_id = wallet.wallet.id
    if invoice_data.out is True and wallet.key_type == KeyType.admin:
        if not invoice_data.bolt11:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Missing BOLT11 invoice",
            )
        payment = await pay_invoice(
            wallet_id=wallet_id,
            payment_request=invoice_data.bolt11,
            extra=invoice_data.extra,
        )
        return payment

    if invoice_data.out:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Invoice (or Admin) key required.",
        )

    # If the payment is not outgoing, we can create a new invoice.
    if invoice_data.fiat_provider:
        return await create_fiat_invoice(wallet_id, invoice_data)

    return await create_wallet_invoice(wallet_id, invoice_data)


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
) -> Payment:
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
            check_callback_url(data.callback)
            r = await client.get(
                data.callback,
                params={"amount": amount_msat, "comment": data.comment},
                timeout=40,
            )
            if r.is_error:
                raise httpx.ConnectError("LNURL callback connection error")
            r.raise_for_status()
        except (httpx.HTTPError, ssl.SSLError) as exc:
            logger.warning(exc)
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Failed to connect to {domain}.",
            ) from exc

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
                f"{domain} returned an invalid invoice. Expected"
                f" {amount_msat} msat, got {invoice.amount_msat}."
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

    payment = await pay_invoice(
        wallet_id=wallet.wallet.id,
        payment_request=params["pr"],
        description=data.description,
        extra=extra,
    )
    return payment


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

    if payment.success:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": True, "preimage": payment.preimage, "details": payment}
        return {"paid": True, "preimage": payment.preimage}

    if payment.failed:
        return {"paid": False, "status": "failed", "details": payment}

    try:
        status = await payment.check_status()
    except Exception:
        if wallet and wallet.id == payment.wallet_id:
            return {"paid": False, "details": payment}
        return {"paid": False}

    if wallet and wallet.id == payment.wallet_id:
        return {
            "paid": payment.success,
            "status": f"{status!s}",
            "preimage": payment.preimage,
            "details": payment,
        }
    return {"paid": payment.success, "preimage": payment.preimage}


@payment_router.post("/decode", status_code=HTTPStatus.OK)
async def api_payments_decode(data: DecodePayment) -> JSONResponse:
    payment_str = data.data
    try:
        if payment_str[:5] == "LNURL":
            url = str(lnurl_decode(payment_str))
            return JSONResponse({"domain": url})
        else:
            invoice = bolt11.decode(payment_str)
            filtered_data = filter_dict_keys(invoice.data, data.filter_fields)
            return JSONResponse(filtered_data)
    except Exception as exc:
        return JSONResponse(
            {"message": f"Failed to decode: {exc!s}"},
            status_code=HTTPStatus.BAD_REQUEST,
        )


@payment_router.post("/{payment_request}/pay-with-nfc", status_code=HTTPStatus.OK)
async def api_payment_pay_with_nfc(
    payment_request: str,
    lnurl_data: PayLnurlWData,
) -> JSONResponse:
    lnurl = lnurl_data.lnurl_w.lower()

    # Follow LUD-17 -> https://github.com/lnurl/luds/blob/luds/17.md
    url = lnurl.replace("lnurlw://", "https://")

    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        try:
            check_callback_url(url)
            lnurl_req = await client.get(url, timeout=10)
            if lnurl_req.is_error:
                return JSONResponse(
                    {"success": False, "detail": "Error loading LNURL request"}
                )

            lnurl_res = lnurl_req.json()

            if lnurl_res.get("status") == "ERROR":
                return JSONResponse({"success": False, "detail": lnurl_res["reason"]})

            if lnurl_res.get("tag") != "withdrawRequest":
                return JSONResponse(
                    {"success": False, "detail": "Invalid LNURL-withdraw"}
                )

            callback_url = lnurl_res["callback"]
            k1 = lnurl_res["k1"]

            callback_req = await client.get(
                callback_url,
                params={"k1": k1, "pr": payment_request},
                timeout=10,
            )
            if callback_req.is_error:
                return JSONResponse(
                    {"success": False, "detail": "Error loading callback request"}
                )

            callback_res = callback_req.json()

            if callback_res.get("status") == "ERROR":
                return JSONResponse(
                    {"success": False, "detail": callback_res["reason"]}
                )
            else:
                return JSONResponse({"success": True, "detail": callback_res})

        except Exception as e:
            return JSONResponse({"success": False, "detail": f"Unexpected error: {e}"})
