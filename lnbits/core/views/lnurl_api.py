from http import HTTPStatus
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from lnurl import (
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlException,
    LnurlPayResponse,
    LnurlResponseException,
    LnurlWithdrawResponse,
)
from lnurl import execute_login as lnurlauth
from lnurl import handle as lnurl_handle
from lnurl.models import LnurlResponseModel
from loguru import logger

from lnbits.core.models import Payment
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_base_invoice_key,
)
from lnbits.helpers import check_callback_url
from lnbits.settings import settings

from ..services import fetch_lnurl_pay_request, pay_invoice

lnurl_router = APIRouter(tags=["LNURL"])


async def _handle(lnurl: str) -> LnurlResponseModel:
    try:
        res = await lnurl_handle(lnurl, user_agent=settings.user_agent, timeout=5)
        if isinstance(res, LnurlErrorResponse):
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=res.reason)
    except LnurlException as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc
    return res


@lnurl_router.get(
    "/api/v1/lnurlscan/{code}",
    dependencies=[Depends(require_base_invoice_key)],
    deprecated=True,
    response_model=LnurlPayResponse
    | LnurlWithdrawResponse
    | LnurlAuthResponse
    | LnurlErrorResponse,
)
async def api_lnurlscan(code: str) -> LnurlResponseModel:
    res = await _handle(code)
    if isinstance(res, LnurlPayResponse | LnurlWithdrawResponse | LnurlAuthResponse):
        check_callback_url(res.callback)
    return res


@lnurl_router.post(
    "/api/v1/lnurlscan",
    dependencies=[Depends(require_base_invoice_key)],
    response_model=LnurlPayResponse
    | LnurlWithdrawResponse
    | LnurlAuthResponse
    | LnurlErrorResponse,
)
async def api_lnurlscan_post(scan: LnurlScan) -> LnurlResponseModel:
    return await _handle(scan.lnurl)


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
    """
    Pay an LNURL payment request.
    Either provice `res` (LnurlPayResponse) or `lnurl` (str) in the `data` object.
    """
    if not data.res and not data.lnurl:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Missing LNURL or LnurlPayResponse data.",
        )

    try:
        res, res2 = await fetch_lnurl_pay_request(data=data, wallet=wallet.wallet)
    except LnurlResponseException as exc:
        logger.warning(exc)
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail=str(exc)
        ) from exc

    extra: dict[str, Any] = {}
    if res2.disposable is False:
        extra["stored"] = True
    if res2.successAction:
        extra["success_action"] = res2.successAction.json()
    if data.comment:
        extra["comment"] = data.comment
    if data.unit and data.unit != "sat":
        extra["fiat_currency"] = data.unit
        extra["fiat_amount"] = data.amount / 1000

    payment = await pay_invoice(
        wallet_id=wallet.wallet.id,
        payment_request=str(res2.pr),
        description=res.metadata.text,
        extra=extra,
    )

    return payment
