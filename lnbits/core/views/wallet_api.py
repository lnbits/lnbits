from http import HTTPStatus
from typing import Optional
from uuid import uuid4

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)

from lnbits.core.crud.wallets import get_wallets_paginated
from lnbits.core.models import CreateWallet, KeyType, User, Wallet
from lnbits.core.models.wallets import WalletsFilters
from lnbits.db import Filters, Page
from lnbits.decorators import (
    WalletTypeInfo,
    check_user_exists,
    parse_filters,
    require_admin_key,
    require_invoice_key,
)
from lnbits.helpers import generate_filter_params_openapi

from ..crud import (
    create_wallet,
    delete_wallet,
    get_wallet,
    update_wallet,
)

wallet_router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@wallet_router.get("")
async def api_wallet(key_info: WalletTypeInfo = Depends(require_invoice_key)):
    res = {
        "name": key_info.wallet.name,
        "balance": key_info.wallet.balance_msat,
    }
    if key_info.key_type == KeyType.admin:
        res["id"] = key_info.wallet.id
    return res


@wallet_router.get(
    "/paginated",
    name="Wallet List",
    summary="get paginated list of user wallets",
    response_description="list of user wallets",
    response_model=Page[Wallet],
    openapi_extra=generate_filter_params_openapi(WalletsFilters),
)
async def api_wallets_paginated(
    user: User = Depends(check_user_exists),
    filters: Filters = Depends(parse_filters(WalletsFilters)),
):
    page = await get_wallets_paginated(
        user_id=user.id,
        filters=filters,
    )

    return page


@wallet_router.put("/{new_name}")
async def api_update_wallet_name(
    new_name: str, key_info: WalletTypeInfo = Depends(require_admin_key)
):
    wallet = await get_wallet(key_info.wallet.id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")
    wallet.name = new_name
    await update_wallet(wallet)
    return {
        "id": wallet.id,
        "name": wallet.name,
        "balance": wallet.balance_msat,
    }


@wallet_router.put("/reset/{wallet_id}")
async def api_reset_wallet_keys(
    wallet_id: str, user: User = Depends(check_user_exists)
) -> Wallet:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != user.id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    wallet.adminkey = uuid4().hex
    wallet.inkey = uuid4().hex
    await update_wallet(wallet)
    return wallet


@wallet_router.patch("")
async def api_update_wallet(
    name: Optional[str] = Body(None),
    icon: Optional[str] = Body(None),
    color: Optional[str] = Body(None),
    currency: Optional[str] = Body(None),
    pinned: Optional[bool] = Body(None),
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    wallet = await get_wallet(key_info.wallet.id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")
    wallet.name = name or wallet.name
    wallet.extra.icon = icon or wallet.extra.icon
    wallet.extra.color = color or wallet.extra.color
    wallet.extra.pinned = pinned if pinned is not None else wallet.extra.pinned
    wallet.currency = currency if currency is not None else wallet.currency
    await update_wallet(wallet)
    return wallet


@wallet_router.delete("/{wallet_id}")
async def api_delete_wallet(
    wallet_id: str, user: User = Depends(check_user_exists)
) -> None:
    wallet = await get_wallet(wallet_id)
    if not wallet or wallet.user != user.id:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    await delete_wallet(
        user_id=wallet.user,
        wallet_id=wallet.id,
    )


@wallet_router.post("")
async def api_create_wallet(
    data: CreateWallet,
    key_info: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    return await create_wallet(user_id=key_info.wallet.user, wallet_name=data.name)
