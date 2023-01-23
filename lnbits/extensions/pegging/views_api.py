from http import HTTPStatus

import httpx
from fastapi import Depends, Query
from lnurl import decode as decode_lnurl
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_latest_payments_by_extension, get_user
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice
from lnbits.core.views.api import api_payment
from lnbits.decorators import WalletTypeInfo, get_key_type, require_admin_key
from lnbits.settings import settings

from . import pegging_ext
from .crud import create_pegging, delete_pegging, get_pegging, get_peggings
from .models import CreatePeggingData


@pegging_ext.get("/api/v1/peggings", status_code=HTTPStatus.OK)
async def api_peggings(
    all_wallets: bool = Query(False), wallet: WalletTypeInfo = Depends(get_key_type)
):
    wallet_ids = [wallet.wallet.id]
    if all_wallets:
        user = await get_user(wallet.wallet.user)
        wallet_ids = user.wallet_ids if user else []

    return [pegging.dict() for pegging in await get_peggings(wallet_ids)]


@pegging_ext.post("/api/v1/peggings", status_code=HTTPStatus.CREATED)
async def api_pegging_create(
    data: CreatePeggingData, wallet: WalletTypeInfo = Depends(get_key_type)
):
    pegging = await create_pegging(wallet_id=wallet.wallet.id, data=data)
    return pegging.dict()


@pegging_ext.delete("/api/v1/peggings/{pegging_id}")
async def api_pegging_delete(
    pegging_id: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    pegging = await get_pegging(pegging_id)

    if not pegging:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pegging does not exist."
        )

    if pegging.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, detail="Not your Pegging."
        )

    await delete_pegging(pegging_id)
    return "", HTTPStatus.NO_CONTENT


@pegging_ext.post(
    "/api/v1/peggings/{pegging_id}/invoices", status_code=HTTPStatus.CREATED
)
async def api_pegging_create_invoice(
    pegging_id: str, amount: int = Query(..., ge=1), memo: str = "", tipAmount: int = 0
) -> dict:

    pegging = await get_pegging(pegging_id)

    if not pegging:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Pegging does not exist."
        )

    if tipAmount > 0:
        amount += tipAmount

    try:
        payment_hash, payment_request = await create_invoice(
            wallet_id=pegging.wallet,
            amount=amount,
            memo=f"{memo} to {pegging.name}" if memo else f"{pegging.name}",
            extra={
                "tag": "pegging",
                "tipAmount": tipAmount,
                "peggingId": pegging_id,
                "amount": amount - tipAmount if tipAmount else False,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return {"payment_hash": payment_hash, "payment_request": payment_request}
