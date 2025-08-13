from http import HTTPStatus
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from lnurl import (
    LnurlResponseException,
    LnurlSuccessResponse,
)
from lnurl import execute_login as lnurlauth
from lnurl import execute_withdraw as lnurl_withdraw
from lnurl import handle as lnurl_handle
from lnurl.models import (
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlPayResponse,
    LnurlResponseModel,
    LnurlWithdrawResponse,
)
from loguru import logger

from lnbits.core.models import CreateLnurlWithdraw, Payment
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import check_callback_url
from lnbits.settings import settings

from ..services import fetch_lnurl_pay_request, pay_invoice

lnurl_router = APIRouter(tags=["LNURL"])


@lnurl_router.get(
    "/api/v1/lnurlscan/{code}",
    dependencies=[Depends(require_invoice_key)],
    deprecated=True,
    response_model=LnurlPayResponse
    | LnurlWithdrawResponse
    | LnurlAuthResponse
    | LnurlErrorResponse,
)
async def api_lnurlscan(code: str) -> LnurlResponseModel:
    try:
        res = await lnurl_handle(code, user_agent=settings.user_agent, timeout=5)
    except LnurlResponseException as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    if isinstance(res, (LnurlPayResponse, LnurlWithdrawResponse, LnurlAuthResponse)):
        check_callback_url(res.callback)
    return res


@lnurl_router.post(
    "/api/v1/lnurlscan",
    dependencies=[Depends(require_invoice_key)],
    response_model=LnurlPayResponse
    | LnurlWithdrawResponse
    | LnurlAuthResponse
    | LnurlErrorResponse,
)
async def api_lnurlscan_post(scan: LnurlScan) -> LnurlResponseModel:
    try:
        res = await lnurl_handle(scan.lnurl, user_agent=settings.user_agent, timeout=5)
    except LnurlResponseException as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc
    return res


@lnurl_router.post("/api/v1/lnurlauth")
async def api_perform_lnurlauth(
    data: LnurlAuthResponse, key_type: WalletTypeInfo = Depends(require_admin_key)
) -> LnurlResponseModel:
    check_callback_url(data.callback)
    try:
        res = await lnurlauth(
            res=data,
            seed=key_type.wallet.adminkey,
            user_agent=settings.user_agent,
            timeout=5,
        )
        return res
    except LnurlResponseException as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc


@lnurl_router.post("/api/v1/payments/lnurl")
async def api_payments_pay_lnurl(
    data: CreateLnurlPayment, wallet: WalletTypeInfo = Depends(require_admin_key)
) -> Payment:
    try:
        res = await fetch_lnurl_pay_request(data=data)
    except LnurlResponseException as exc:
        logger.warning(exc)
        msg = f"Failed to connect to {data.res.callback}."
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg) from exc

    extra: dict[str, Any] = {}
    if res.success_action:
        extra["success_action"] = res.success_action.json()
    if data.comment:
        extra["comment"] = data.comment
    if data.unit and data.unit != "sat":
        extra["fiat_currency"] = data.unit
        extra["fiat_amount"] = data.amount / 1000

    payment = await pay_invoice(
        wallet_id=wallet.wallet.id,
        payment_request=str(res.pr),
        description=data.res.metadata.text,
        extra=extra,
    )

    return payment


@lnurl_router.post(
    "/api/v1/payments/{payment_request}/pay-with-nfc", status_code=HTTPStatus.OK
)
async def api_payment_pay_with_nfc(
    payment_request: str,
    lnurl_data: CreateLnurlWithdraw,
) -> LnurlErrorResponse | LnurlSuccessResponse:
    if not lnurl_data.lnurl_w.lud17:
        return LnurlErrorResponse(reason="LNURL-withdraw lud17 not provided.")
    try:
        url = lnurl_data.lnurl_w.lud17
        res = await lnurl_handle(url, user_agent=settings.user_agent, timeout=10)
    except (LnurlResponseException, Exception):
        return LnurlErrorResponse(reason="Invalid LNURL-withdraw response.")

    if not isinstance(res, LnurlWithdrawResponse):
        return LnurlErrorResponse(reason="Invalid LNURL-withdraw response.")
    try:
        check_callback_url(res.callback)
    except ValueError as exc:
        return LnurlErrorResponse(reason=f"Invalid callback URL: {exc!s}")

    try:
        res2 = await lnurl_withdraw(
            res, payment_request, user_agent=settings.user_agent, timeout=10
        )
    except (LnurlResponseException, Exception) as exc:
        logger.warning(exc)
        return LnurlErrorResponse(reason=str(exc))
    if not isinstance(res2, (LnurlSuccessResponse, LnurlErrorResponse)):
        return LnurlErrorResponse(reason="Invalid LNURL-withdraw response.")

    return res2
