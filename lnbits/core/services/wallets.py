from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet, get_standalone_wallet, update_wallet
from lnbits.core.models.wallets import (
    Wallet,
    WalletSharePermission,
    WalletType,
)
from lnbits.db import Connection


async def create_advanced_wallet(
    user_id: str,
    wallet_name: str | None = None,
    wallet_type: WalletType = WalletType.LIGHTNING,
    shared_wallet_id: str | None = None,
    conn: Connection | None = None,
) -> Wallet:
    if wallet_type == WalletType.LIGHTNING:
        return await create_wallet(
            user_id=user_id,
            wallet_name=wallet_name,
            conn=conn,
        )

    if wallet_type == WalletType.LIGHTNING_SHARED:
        return await create_lightinng_shared_wallet(
            user_id, wallet_name, shared_wallet_id, conn=conn
        )


async def create_lightinng_shared_wallet(
    user_id: str,
    wallet_name: str | None = None,
    shared_wallet_id: str | None = None,
    conn: Connection | None = None,
) -> Wallet:
    if not shared_wallet_id:
        raise ValueError("Shared wallet ID is required")
    shared_wallet = await get_standalone_wallet(shared_wallet_id, conn=conn)
    if not shared_wallet:
        raise ValueError("Shared wallet does not exist")
    # check pending requests and if user already has access to that wallet
    wallet = await create_wallet(
        user_id=user_id,
        wallet_name=wallet_name,
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id=shared_wallet_id,
        conn=conn,
    )
    user = await get_account(user_id, conn=conn)
    if not user:
        raise ValueError("Invalid user id.")
    shared_wallet.extra.shared_with.append(
        WalletSharePermission(
            username=user.username or user.email or "Anonymous", wallet_id=wallet.id
        )
    )
    await update_wallet(shared_wallet, conn=conn)
    wallet.mirror_shared_wallet(shared_wallet)
    return wallet
