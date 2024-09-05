from typing import Optional

from fastapi import (
    APIRouter,
    Body,
    Depends,
)

from lnbits.core.models import (
    CreateWallet,
    KeyType,
    Wallet,
)
from lnbits.decorators import (
    WalletTypeInfo,
    require_admin_key,
    require_invoice_key,
)

from ..crud import (
    create_wallet,
    delete_wallet,
    update_wallet,
)

wallet_router = APIRouter(prefix="/api/v1/wallet", tags=["Wallet"])


@wallet_router.get("")
async def api_wallet(wallet: WalletTypeInfo = Depends(require_invoice_key)):
    res = {
        "name": wallet.wallet.name,
        "balance": wallet.wallet.balance_msat,
    }
    if wallet.key_type == KeyType.admin:
        res["id"] = wallet.wallet.id
    return res


@wallet_router.put("/{new_name}")
async def api_update_wallet_name(
    new_name: str, wallet: WalletTypeInfo = Depends(require_admin_key)
):
    await update_wallet(wallet.wallet.id, new_name)
    return {
        "id": wallet.wallet.id,
        "name": wallet.wallet.name,
        "balance": wallet.wallet.balance_msat,
    }


@wallet_router.patch("", response_model=Wallet)
async def api_update_wallet(
    name: Optional[str] = Body(None),
    currency: Optional[str] = Body(None),
    wallet: WalletTypeInfo = Depends(require_admin_key),
):
    return await update_wallet(wallet.wallet.id, name, currency)


@wallet_router.delete("")
async def api_delete_wallet(
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> None:
    await delete_wallet(
        user_id=wallet.wallet.user,
        wallet_id=wallet.wallet.id,
    )


@wallet_router.post("", response_model=Wallet)
async def api_create_wallet(
    data: CreateWallet,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> Wallet:
    return await create_wallet(user_id=wallet.wallet.user, wallet_name=data.name)
