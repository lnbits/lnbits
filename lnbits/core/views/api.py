from http import HTTPStatus
from io import BytesIO
from time import time
from typing import Any

import pyqrcode
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from lnbits.core.models import (
    BaseWallet,
    ConversionData,
    CreateWallet,
    User,
    Wallet,
)
from lnbits.core.models.users import AccountId
from lnbits.decorators import (
    check_account_exists,
    check_account_id_exists,
    check_user_exists,
)
from lnbits.settings import settings
from lnbits.utils.exchange_rates import (
    allowed_currencies,
    fiat_amount_as_satoshis,
    get_fiat_rate_and_price_satoshis,
    satoshis_amount_as_fiat,
)
from lnbits.wallets import get_funding_source
from lnbits.wallets.base import StatusResponse

from ..services import create_user_account

api_router = APIRouter(tags=["Core"])


@api_router.get("/api/v1/health", status_code=HTTPStatus.OK)
async def health() -> dict:
    return {
        "server_time": int(time()),
        "up_time": settings.lnbits_server_up_time,
    }


@api_router.get("/api/v1/status", status_code=HTTPStatus.OK)
async def health_check(
    account_id: AccountId = Depends(check_account_id_exists),
) -> dict:
    stat: dict[str, Any] = {
        "server_time": int(time()),
        "up_time": settings.lnbits_server_up_time,
        "up_time_seconds": int(time() - settings.server_startup_time),
    }

    stat["version"] = settings.version
    if not account_id.is_admin_id:
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
    "/api/v1/rate/history",
    dependencies=[Depends(check_account_exists)],
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


@api_router.get("/api/v1/qrcode", response_class=StreamingResponse)
@api_router.get("/api/v1/qrcode/{data}", response_class=StreamingResponse)
async def img(data: str):
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
