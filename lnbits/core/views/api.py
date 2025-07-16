from http import HTTPStatus
from io import BytesIO
from time import time
from typing import Any

import pyqrcode
from bolt11 import decode as bolt11_decode
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import StreamingResponse
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

from lnbits.core.models import (
    BaseWallet,
    ConversionData,
    CreateLnurlWithdraw,
    CreateWallet,
    Payment,
    User,
    Wallet,
)
from lnbits.core.models.lnurl import CreateLnurlPayment
from lnbits.decorators import (
    WalletTypeInfo,
    check_user_exists,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import check_callback_url
from lnbits.settings import settings
from lnbits.utils.exchange_rates import (
    allowed_currencies,
    fiat_amount_as_satoshis,
    get_fiat_rate_and_price_satoshis,
    satoshis_amount_as_fiat,
)
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import StatusResponse

from ..services import create_user_account, pay_invoice

api_router = APIRouter(tags=["Core"])


@api_router.get("/api/v1/health", status_code=HTTPStatus.OK)
async def health() -> dict:
    return {
        "server_time": int(time()),
        "up_time": settings.lnbits_server_up_time,
    }


@api_router.get("/api/v1/status", status_code=HTTPStatus.OK)
async def health_check(user: User = Depends(check_user_exists)) -> dict:
    stat: dict[str, Any] = {
        "server_time": int(time()),
        "up_time": settings.lnbits_server_up_time,
        "up_time_seconds": int(time() - settings.server_startup_time),
    }

    stat["version"] = settings.version
    if not user.admin:
        return stat

    funding_source = get_funding_source()
    stat["funding_source"] = funding_source.__class__.__name__

    status: StatusResponse = await funding_source.status()
    stat["funding_source_error"] = status.error_message
    stat["funding_source_balance_msat"] = status.balance_msat

    return stat


@api_router.get(
    "/api/v1/wallets",
    name="Wallets",
    description="Get basic info for all of user's wallets.",
    response_model=list[BaseWallet],
)
async def api_wallets(user: User = Depends(check_user_exists)) -> list[Wallet]:
    return user.wallets


@api_router.post("/api/v1/account")
async def api_create_account(data: CreateWallet) -> Wallet:
    user = await create_user_account(wallet_name=data.name)
    return user.wallets[0]


@api_router.get(
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


@api_router.post("/api/v1/lnurlauth")
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


@api_router.post("/api/v1/payments/lnurl")
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


@api_router.post(
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


@api_router.get(
    "/api/v1/rate/history",
    dependencies=[Depends(check_user_exists)],
)
async def api_exchange_rate_history() -> list[dict]:
    return settings.lnbits_exchange_rate_history


@api_router.get("/api/v1/rate/{currency}")
async def api_check_fiat_rate(currency: str) -> dict[str, float]:
    rate, price = await get_fiat_rate_and_price_satoshis(currency)
    return {"rate": rate, "price": price}


@api_router.get("/api/v1/currencies")
async def api_list_currencies_available() -> list[str]:
    return allowed_currencies()


@api_router.post("/api/v1/conversion")
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


@api_router.get("/api/v1/qrcode/{data}", response_class=StreamingResponse)
async def img(data):
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
