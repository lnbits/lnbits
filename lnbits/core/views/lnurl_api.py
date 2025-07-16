from http import HTTPStatus
from typing import Any

from bolt11 import decode as bolt11_decode
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
from lnurl import execute_pay_request as lnurlp
from lnurl import execute_withdraw as lnurl_withdraw
from lnurl import handle as lnurl_handle
from lnurl.models import (
    LnurlAuthResponse,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayResponse,
    LnurlResponseModel,
    LnurlWithdrawResponse,
)
from loguru import logger

from lnbits.core.models import CreateLnurlWithdraw, Payment
from lnbits.core.models.lnurl import CreateLnurlPayment
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis

from ..services import pay_invoice

lnurl_router = APIRouter(tags=["LNURL"])


@lnurl_router.get(
    "/api/v1/lnurlscan/{code}",
    dependencies=[Depends(require_invoice_key)],
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

    if data.unit and data.unit != "sat":
        # shift to float with 2 decimal places
        amount = round(data.amount / 1000, 2)
        amount_msat = await fiat_amount_as_satoshis(amount, data.unit)
        amount_msat *= 1000
    else:
        amount_msat = data.amount

    try:
        res = await lnurlp(
            data.res,
            msat=str(amount_msat),
            user_agent=settings.user_agent,
            timeout=5,
        )
    except LnurlResponseException as exc:
        logger.debug(str(exc))
        msg = f"Failed to connect to {data.res.callback}."
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg) from exc

    if not isinstance(res, LnurlPayActionResponse):
        msg = f"lnurl response is not a LnurlPayActionResponse: {res}"
        logger.warning(msg)
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=msg)

    invoice = bolt11_decode(res.pr)

    if invoice.amount_msat != amount_msat:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"{data.res.callback} returned an invalid invoice. Expected"
                f" {amount_msat} msat, got {invoice.amount_msat}."
            ),
        )

    if invoice.description:
        description = invoice.description
    else:
        # If the invoice description is empty, use the metadata from the lnurl response
        description = data.res.metadata.text

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
        description=description,
        extra=extra,
    )
    return payment


@lnurl_router.post(
    "/api/v1/payments/{payment_request}/pay-with-nfc", status_code=HTTPStatus.OK
)
async def api_payment_pay_with_nfc(
    payment_request: str,
    lnurl_data: CreateLnurlWithdraw,
) -> LnurlSuccessResponse | LnurlErrorResponse:
    try:
        res = await lnurl_handle(
            lnurl_data.lnurl_w.callback_url, user_agent=settings.user_agent, timeout=10
        )
    except LnurlResponseException as exc:
        logger.warning(exc)
        return LnurlErrorResponse(
            reason=f"Failed to connect to {lnurl_data.lnurl_w.callback_url}: {exc!s}"
        )
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
    except LnurlResponseException as exc:
        logger.warning(exc)
        return LnurlErrorResponse(
            reason=f"Failed to connect to {lnurl_data.lnurl_w.callback_url}: {exc!s}"
        )
    if not isinstance(res2, (LnurlSuccessResponse, LnurlErrorResponse)):
        return LnurlErrorResponse(reason="Invalid LNURL-withdraw response.")

    return res2
