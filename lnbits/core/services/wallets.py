from lnbits.core.crud.users import (
    get_account,
    get_account_by_username_or_email,
    update_account,
)
from lnbits.core.crud.wallets import (
    create_wallet,
    force_delete_wallet,
    get_standalone_wallet,
    get_wallet,
    update_wallet,
)
from lnbits.core.models.misc import SimpleStatus
from lnbits.core.models.users import Account
from lnbits.core.models.wallets import (
    Wallet,
    WalletSharePermission,
    WalletShareStatus,
    WalletType,
)
from lnbits.db import Connection
from lnbits.helpers import sha256s


async def invite_to_wallet(source_wallet: Wallet, data: WalletSharePermission):
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Only lightning wallets can be shared.")
    if not data.username:
        raise ValueError("Username or email missing.")
    invited_user = await get_account_by_username_or_email(data.username)
    if not invited_user:
        raise ValueError("Invited user not found.")

    request_id = sha256s(invited_user.id)
    share = source_wallet.extra.find_share_by_id(request_id)
    if share:
        raise ValueError("User already invited to this wallet.")

    invite_request = source_wallet.extra.invite_user_to_shared_wallet(
        request_id=request_id,
        request_type=WalletShareStatus.INVITE_SENT,
        username=data.username,
        wallet_id=source_wallet.id,
        permissions=data.permissions,
    )
    await update_wallet(source_wallet)

    wallet_owner = await get_account(source_wallet.user)
    if not wallet_owner:
        raise ValueError("Cannot find wallet owner.")
    invited_user.extra.add_wallet_invite_request(
        request_id=request_id,
        from_user_name=wallet_owner.username or wallet_owner.email,
        to_wallet_id=source_wallet.id,
        to_wallet_name=source_wallet.name,
    )
    await update_account(invited_user)

    return invite_request


async def accept_wallet_invitation(source_wallet: Wallet, data: WalletSharePermission):
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Only lightning wallets can be shared.")
    if not data.wallet_id:
        raise ValueError("Wallet ID missing.")

    share = source_wallet.extra.find_share_for_wallet(data.wallet_id)
    if not share:
        raise ValueError("Share not found")
    if not share.wallet_id:
        raise ValueError("Wallet ID missing in share.")

    mirror_wallet = await get_wallet(share.wallet_id)
    if not mirror_wallet:
        raise ValueError("Target wallet not found")
    if not mirror_wallet.is_lightning_shared_wallet:
        raise ValueError("Target wallet is not a shared wallet.")

    share.approve(permissions=data.permissions)
    await update_wallet(source_wallet)
    return share


async def delete_wallet_share(source_wallet: Wallet, request_id: str):
    if not source_wallet.is_lightning_wallet:
        raise ValueError("Source wallet is not a lightning wallet.")

    share = source_wallet.extra.find_share_by_id(request_id)
    if not share:
        raise ValueError("Wallet share not found.")
    source_wallet.extra.remove_share_by_id(request_id)
    mirror_wallet = await get_wallet(share.wallet_id) if share.wallet_id else None
    if not mirror_wallet:
        await update_wallet(source_wallet)
        return SimpleStatus(
            success=True, message="Permission removed. Target wallet not found."
        )

    if not mirror_wallet.is_lightning_shared_wallet:
        raise ValueError("Target wallet is not a shared lightning wallet.")

    if mirror_wallet.shared_wallet_id != source_wallet.id:
        raise ValueError("Not the owner of the shared wallet.")

    await force_delete_wallet(mirror_wallet.id)

    await update_wallet(source_wallet)
    return SimpleStatus(success=True, message="Permission removed.")


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

    invited_user = await get_account(user_id, conn=conn)
    if not invited_user:
        raise ValueError("Invalid invited user id.")

    existing_request = shared_wallet.extra.find_share_by_id(sha256s(user_id))
    if not existing_request:
        raise ValueError("No invitation found for this invited user.")

    return await _accept_invitation_to_shared_wallet(
        shared_wallet, invited_user, conn=conn
    )


async def _accept_invitation_to_shared_wallet(
    shared_wallet: Wallet,
    invited_user: Account,
    conn: Connection | None = None,
) -> Wallet:
    existing_request = shared_wallet.extra.find_share_by_id(sha256s(invited_user.id))
    if not existing_request:
        raise ValueError("Missing share request.")
    if existing_request.status == WalletShareStatus.REQUEST_ACCESS:
        raise ValueError("You have already requested access to this wallet.")
    if existing_request.status == WalletShareStatus.APPROVED:
        raise ValueError("This wallet is already shared with you.")
    if existing_request.status != WalletShareStatus.INVITE_SENT:
        raise ValueError("Unknown request type.")

    invited_user.extra.remove_wallet_invite_request(sha256s(invited_user.id))
    await update_account(invited_user)

    mirror_wallet = await create_wallet(
        user_id=invited_user.id,
        wallet_name=shared_wallet.name,
        wallet_type=WalletType.LIGHTNING_SHARED,
        shared_wallet_id=shared_wallet.id,
        conn=conn,
    )
    existing_request.approve(wallet_id=mirror_wallet.id)
    await update_wallet(shared_wallet, conn=conn)
    mirror_wallet.mirror_shared_wallet(shared_wallet)
    return mirror_wallet
