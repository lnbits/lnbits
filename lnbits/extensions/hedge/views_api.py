from http import HTTPStatus

from fastapi.param_functions import Query
from fastapi.params import Depends
from starlette.exceptions import HTTPException

from lnbits.core.crud import get_user
from lnbits.decorators import WalletTypeInfo, get_key_type

from . import hedge_ext
from .crud import (
    create_hedge,
    delete_hedge,
    get_hedge,
    get_hedges,
    update_hedge,
)

from .models import createHedgedWallet


@hedge_ext.post("/api/v1/hedges")
async def api_create_hedge(data: createHedgedWallet):
    """Create a hedge, which holds data about how/where to post tips"""
    try:
        hedge = await create_hedge(data)
    except Exception as e:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))

    return hedge.dict()


async def user_from_wallet(wallet: WalletTypeInfo = Depends(get_key_type)):
    return wallet.wallet.user


@hedge_ext.get("/api/v1/hedges")
async def api_get_hedges(wallet: WalletTypeInfo = Depends(get_key_type)):
    """Return list of all hedges assigned to wallet with given invoice key"""
    wallet_ids = (await get_user(wallet.wallet.user)).wallet_ids
    hedges = []
    for wallet_id in wallet_ids:
        new_hedges = await get_hedges(wallet_id)
        hedges += new_hedges if new_hedges else []
    return [hedge.dict() for hedge in hedges] if hedges else []


@hedge_ext.put("/api/v1/hedges/{hedge_id}")
async def api_update_hedge(
    wallet: WalletTypeInfo = Depends(get_key_type), hedge_id: str = Query(None)
):
    """Update a hedge with the data given in the request"""
    if hedge_id:
        hedge = await get_hedge(hedge_id)

        if not hedge:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="HedgedWallet does not exist."
            )

        if hedge.wallet != wallet.wallet.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, detail="Not your hedge."
            )

        hedge = await update_hedge(hedge_id, **data)
    else:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST, detail="No hedge ID specified"
        )
    return hedge.dict()


@hedge_ext.delete("/api/v1/hedges/{hedge_id}")
async def api_delete_hedge(
    wallet: WalletTypeInfo = Depends(get_key_type), hedge_id: str = Query(None)
):
    """Delete the hedge with the given hedge_id"""
    hedge = await get_hedge(hedge_id)
    if not hedge:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="No hedge with this ID!"
        )
    if hedge.wallet != wallet.wallet.id:

        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Not authorized to delete this hedge!",
        )
    await delete_hedge(hedge_id)

    return "", HTTPStatus.NO_CONTENT
