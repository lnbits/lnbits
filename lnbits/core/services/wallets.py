from lnbits.core.crud.users import get_account
from lnbits.core.crud.wallets import create_wallet, get_standalone_wallet, update_wallet
from lnbits.core.models.wallets import (
    Wallet,
    WalletSharePermission,
    WalletType,
)
from lnbits.db import Connection


async def create_lightning_shared_wallet(
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

    if not shared_wallet.is_lightning_wallet:
        raise ValueError("Shared wallet is not a lightning wallet.")

    if shared_wallet.user == user_id:
        raise ValueError("Cannot mirror your own wallet.")

    user = await get_account(user_id, conn=conn)
    if not user:
        raise ValueError("Invalid user id.")

    if not user.username or not user.email:
        raise ValueError("You must have a username or email to mirror wallet.")

    print("### user.username or user.email", user.username, user.email)
    existing_request = shared_wallet.extra.find_share_for_user(
        user.username or user.email
    )
    print("### existing_request", existing_request)

    if existing_request:
        raise ValueError("A share request for this wallet already exists.")

    # check pending requests and if user already has access to that wallet
    mirror_wallet = await create_wallet(
        user_id=user_id,
        wallet_name=wallet_name,
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id=shared_wallet_id,
        conn=conn,
    )

    shared_wallet.extra.shared_with.append(
        WalletSharePermission(
            wallet_id=mirror_wallet.id,
            username=user.username or user.email or "Anonymous",
        )
    )
    await update_wallet(shared_wallet, conn=conn)
    mirror_wallet.mirror_shared_wallet(shared_wallet)
    return mirror_wallet
