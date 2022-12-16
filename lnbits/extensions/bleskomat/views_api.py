from http import HTTPStatus

from fastapi import Depends, Query
from loguru import logger
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, require_admin_key
from lnbits.extensions.bleskomat.models import CreateBleskomat

from . import bleskomat_ext
from .crud import (
    create_bleskomat,
    delete_bleskomat,
    get_bleskomat,
    get_bleskomats,
    update_bleskomat,
)
from .exchange_rates import fetch_fiat_exchange_rate


@bleskomat_ext.get("/api/v1/bleskomats")
async def api_bleskomats(
    wallet: WalletTypeInfo = Depends(require_admin_key),
    all_wallets: bool = Query(False),
):
    wallet_ids = [wallet.wallet.id]

    if all_wallets:
        wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids

    return [bleskomat.dict() for bleskomat in await get_bleskomats(wallet_ids)]


@bleskomat_ext.get("/api/v1/bleskomat/{bleskomat_id}")
async def api_bleskomat_retrieve(
    bleskomat_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    bleskomat = await get_bleskomat(bleskomat_id)

    if not bleskomat or bleskomat.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Bleskomat configuration not found.",
        )

    return bleskomat.dict()


@bleskomat_ext.post("/api/v1/bleskomat")
@bleskomat_ext.put("/api/v1/bleskomat/{bleskomat_id}")
async def api_bleskomat_create_or_update(
    data: CreateBleskomat,
    wallet: WalletTypeInfo = Depends(require_admin_key),
    bleskomat_id=None,
):
    try:
        fiat_currency = data.fiat_currency
        exchange_rate_provider = data.exchange_rate_provider
        await fetch_fiat_exchange_rate(
            currency=fiat_currency, provider=exchange_rate_provider
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f'Failed to fetch BTC/{fiat_currency} currency pair from "{exchange_rate_provider}"',
        )

    if bleskomat_id:
        bleskomat = await get_bleskomat(bleskomat_id)
        if not bleskomat or bleskomat.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="Bleskomat configuration not found.",
            )

        bleskomat = await update_bleskomat(bleskomat_id, **data.dict())
    else:
        bleskomat = await create_bleskomat(wallet_id=wallet.wallet.id, data=data)

    return bleskomat.dict()


@bleskomat_ext.delete("/api/v1/bleskomat/{bleskomat_id}")
async def api_bleskomat_delete(
    bleskomat_id, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    bleskomat = await get_bleskomat(bleskomat_id)

    if not bleskomat or bleskomat.wallet != wallet.wallet.id:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Bleskomat configuration not found.",
        )

    await delete_bleskomat(bleskomat_id)
    return "", HTTPStatus.NO_CONTENT
