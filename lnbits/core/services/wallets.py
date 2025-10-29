from lnbits.core.crud.users import get_account, update_account
from lnbits.core.crud.wallets import create_wallet, get_standalone_wallet, update_wallet
from lnbits.core.models.wallets import (
    Wallet,
    WalletShareStatus,
    WalletType,
)
from lnbits.db import Connection


async def create_lightning_shared_wallet(
    user_id: str,
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

    existing_request = shared_wallet.extra.find_share_for_user(user_id)

    if existing_request:
        if existing_request.status == WalletShareStatus.REQUEST_ACCESS:
            raise ValueError("You have already requested access to this wallet.")
        if existing_request.status == WalletShareStatus.APPROVED:
            raise ValueError("This wallet is already shared with you.")
        if existing_request.status != WalletShareStatus.INVITE_SENT:
            raise ValueError("Unknown request type.")

        user.extra.remove_wallet_invite_request(from_user_id=user_id)
        await update_account(user)

        mirror_wallet = await create_wallet(
            user_id=user_id,
            wallet_name=shared_wallet.name,
            wallet_type=WalletType.LIGHTNING_SHARED,
            shared_wallet_id=shared_wallet.id,
            conn=conn,
        )
        existing_request.approve(wallet_id=mirror_wallet.id)
        await update_wallet(shared_wallet, conn=conn)
        mirror_wallet.mirror_shared_wallet(shared_wallet)
        return mirror_wallet

    return await _create_new_lightning_shared_wallet(
        user_id=user_id,
        username=user.username or user.email or "Anonymous",
        shared_wallet=shared_wallet,
    )


async def _create_new_lightning_shared_wallet(
    user_id: str,
    username: str,
    shared_wallet: Wallet,
    conn: Connection | None = None,
) -> Wallet:

    mirror_wallet = await create_wallet(
        user_id=user_id,
        wallet_name=shared_wallet.name,
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id=shared_wallet.id,
        conn=conn,
    )

    shared_wallet.extra.add_share_request(
        user_id=user_id,
        username=username,
        wallet_id=mirror_wallet.id,
        request_type=WalletShareStatus.REQUEST_ACCESS,
    )

    await update_wallet(shared_wallet, conn=conn)
    mirror_wallet.mirror_shared_wallet(shared_wallet)
    return mirror_wallet
