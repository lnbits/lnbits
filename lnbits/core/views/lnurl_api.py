from http import HTTPStatus
from typing import Any

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
from ..services.lightning_address import (
    ExtensionLnAddressStatus,
    fetch_extension_lnurlp_response,
    is_safe_lnurlp_username,
    split_tagged_local_part,
    wallet_lightning_address_callback,
    wallet_lightning_address_response,
)
from ..services.lnurl import execute_login as lnurlauth
from ..services.lnurl import handle as lnurl_handle

lnurl_router = APIRouter(tags=["LNURL"])


@lnurl_router.get(
    "/.well-known/lnurlp/{username}",
    name="lnurl.api_wallet_lightning_address_response",
    openapi_extra={"x-lnbits-local-lnurl": True},
)
async def api_wallet_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    if settings.lnbits_ln_address_mode == "core_first":
        return await _core_first_lightning_address_response(username, request)

    return await _extension_first_lightning_address_response(username, request)


@lnurl_router.get(
    "/api/v1/lnurl/wallet/{username}/cb",
    name="lnurl.api_wallet_lightning_address_callback",
    openapi_extra={"x-lnbits-local-lnurl": True},
)
async def api_wallet_lightning_address_callback(
    username: str, request: Request, amount: int = Query(...)
) -> LnurlErrorResponse | Any:
    return await wallet_lightning_address_callback(username, request, amount)


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
        check_callback_url(str(res.callback))
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
    check_callback_url(str(data.callback))
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


async def _core_first_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    core_resp = await wallet_lightning_address_response(username, request)
    if core_resp.ok:
        return core_resp

    _, ext_resp = await _probe_request_extension_lnurlp(username.lower(), request)
    if ext_resp and ext_resp.ok:
        return ext_resp
    return core_resp


async def _extension_first_lightning_address_response(
    username: str, request: Request
) -> LnurlPayResponse | LnurlErrorResponse:
    lower_username = username.lower()
    status, ext_resp = await _probe_request_extension_lnurlp(lower_username, request)
    if ext_resp and ext_resp.ok:
        return ext_resp

    if settings.lnbits_ln_address_mode == "extension_only":
        return LnurlErrorResponse(
            reason="Lightning addresses are not supported on this instance."
        )

    if status == ExtensionLnAddressStatus.UNAVAILABLE:
        return LnurlErrorResponse(reason="Lightning address not found.")

    base_local_part, _ = split_tagged_local_part(username)
    if lower_username != base_local_part and await _extension_owns_or_blocks_base(
        base_local_part, request
    ):
        return ext_resp or LnurlErrorResponse(reason="Lightning address not found.")

    return await wallet_lightning_address_response(username, request)


async def _extension_owns_or_blocks_base(
    base_local_part: str, request: Request
) -> bool:
    base_status, base_resp = await _probe_request_extension_lnurlp(
        base_local_part, request
    )
    return bool(
        (base_resp and base_resp.ok)
        or base_status == ExtensionLnAddressStatus.UNAVAILABLE
    )


async def _probe_request_extension_lnurlp(
    local_part: str, request: Request
) -> tuple[ExtensionLnAddressStatus, LnurlPayResponse | LnurlErrorResponse | None]:
    if not is_safe_lnurlp_username(local_part):
        return ExtensionLnAddressStatus.AVAILABLE, None

    req_headers = request["headers"] if "headers" in request else []
    well_known_path = f"/.well-known/lnurlp/{local_part}"
    redirect = settings.find_extension_redirect(well_known_path, req_headers)
    if not redirect:
        return ExtensionLnAddressStatus.AVAILABLE, None

    return await fetch_extension_lnurlp_response(
        redirect,
        well_known_path,
        app=request.app,
        base_url=str(request.base_url),
    )
