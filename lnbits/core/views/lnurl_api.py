from http import HTTPStatus
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
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
from pydantic import ValidationError

from lnbits.core.models import Payment
from lnbits.core.models.lnurl import CreateLnurlPayment, LnurlScan
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_base_invoice_key,
)
from lnbits.helpers import check_callback_url
from lnbits.settings import RedirectPath, settings

from ..services import fetch_lnurl_pay_request, pay_invoice
from ..services.lightning_address import (
    wallet_lightning_address_callback,
    wallet_lightning_address_response,
)

lnurl_router = APIRouter(tags=["LNURL"])


@lnurl_router.get(
    "/.well-known/lnurlp/{username}",
    name="lnurl.api_wallet_lightning_address_response",
)
async def api_wallet_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    if settings.lnbits_ln_address_mode in ["extension_first", "extension_only"]:
        req_headers = request["headers"] if "headers" in request else []
        redirect = settings.find_extension_redirect(request.url.path, req_headers)
        if redirect:
            resp = await _check_extension_well_known(redirect, request)
            if resp and resp.ok:
                return resp

    if settings.lnbits_ln_address_mode == "extension_only":
        return LnurlErrorResponse(
            reason="Lightning addresses are not supported on this instance."
        )

    return await wallet_lightning_address_response(username, request)


@lnurl_router.get(
    "/api/v1/lnurl/wallet/{username}/cb",
    name="lnurl.api_wallet_lightning_address_callback",
)
async def api_wallet_lightning_address_callback(
    username: str, request: Request, amount: int = Query(...)
) -> LnurlErrorResponse | Any:
    return await wallet_lightning_address_callback(username, request, amount)


async def _handle(lnurl: str) -> LnurlResponseModel:
    try:
        if "@" in lnurl:  # lower case lightning addresses
            lnurl = lnurl.lower()
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


async def _check_extension_well_known(
    redirect: RedirectPath, request: Request
) -> LnurlPayResponse | LnurlErrorResponse | None:
    target_path = redirect.new_path_from(request.url.path)

    transport = httpx.ASGITransport(app=request.app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url=str(request.base_url),
        ) as client:
            response = await client.get(
                target_path,
                headers={"accept": "application/json"},
            )

        response.raise_for_status()
        response_data = response.json()
        try:
            return LnurlPayResponse.parse_obj(response_data)
        except ValidationError:
            return LnurlErrorResponse.parse_obj(response_data)
    except Exception as exc:
        logger.warning(
            f"Failed to fetch LNURL response Extension redirect {target_path}: {exc}"
        )
        return None
