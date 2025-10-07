from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.crud import get_account
from lnbits.core.db import db
from lnbits.core.models import User, WalletTypeInfo
from lnbits.core.models.wallet_shares import (
    CreateWalletShare,
    UpdateWalletSharePermissions,
    WalletShare,
)
from lnbits.decorators import check_user_exists, require_admin_key

from ..crud.wallet_shares import (
    accept_wallet_share,
    create_wallet_share,
    get_user_shared_wallets,
    get_wallet_share,
    get_wallet_shares,
    leave_wallet_share,
    reject_wallet_share,
    revoke_wallet_share,
    update_wallet_share_permissions,
)

wallet_shares_router = APIRouter(prefix="/api/v1/wallet_shares", tags=["Wallet Shares"])


@wallet_shares_router.get("/health")
async def health_check():
    """Test endpoint to verify router is working"""
    return {"status": "ok"}


@wallet_shares_router.post("/{wallet_id}")
async def api_create_wallet_share(
    wallet_id: str,
    data: CreateWalletShare,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """
    Share a wallet with another user.
    Only the wallet owner can share their wallet.
    """
    # Verify this is the correct wallet
    if wallet.wallet.id != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Admin key does not match wallet ID",
        )

    # Verify the recipient user exists (try as username first, then as ID)
    from lnbits.core.crud import get_account_by_username

    recipient = await get_account_by_username(data.user_id)
    if not recipient:
        # Try as user ID instead
        recipient = await get_account(data.user_id)

    if not recipient:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"User '{data.user_id}' not found",
        )

    # Don't allow sharing with self (check after resolving username to user ID)
    if recipient.id == wallet.wallet.user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot share wallet with yourself",
        )

    # Use the actual user ID from the account, not the input (which might be username)
    share_data = CreateWalletShare(user_id=recipient.id, permissions=data.permissions)

    async with db.connect() as conn:
        # Check if wallet is already shared with this user
        from ..crud.wallet_shares import get_wallet_share, get_wallet_shares
        from ..models.wallet_shares import WalletShareStatus

        existing_shares = await get_wallet_shares(conn, wallet_id)

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Re-share check: wallet_id={wallet_id}, recipient_id={recipient.id}")
        logger.info(f"Existing shares count: {len(existing_shares)}")
        for share in existing_shares:
            logger.info(f"  Share: user_id={share.user_id}, status={share.status}")

        existing_share = next(
            (s for s in existing_shares if s.user_id == recipient.id), None
        )

        logger.info(f"Found existing share: {existing_share is not None}")

        if existing_share:
            if existing_share.status in (
                WalletShareStatus.PENDING,
                WalletShareStatus.ACCEPTED,
            ):
                # Can't re-share if already pending or accepted
                raise HTTPException(
                    status_code=HTTPStatus.CONFLICT,
                    detail=(
                        "Wallet is already shared with this user. "
                        "Edit their permissions in the Current Shares section."
                    ),
                )
            else:
                # Re-share: Update existing revoked/rejected/left share to pending
                await conn.execute(
                    """
                    UPDATE wallet_shares
                    SET status = :status, permissions = :permissions,
                        status_updated_at = :status_updated_at
                    WHERE id = :share_id
                    """,
                    {
                        "status": WalletShareStatus.PENDING,
                        "permissions": share_data.permissions,
                        "status_updated_at": datetime.now(timezone.utc),
                        "share_id": existing_share.id,
                    },
                )
                updated_share = await get_wallet_share(conn, existing_share.id)
                return {"share": updated_share, "created": False}
        else:
            # Create new share
            share = await create_wallet_share(
                conn, wallet_id, share_data, wallet.wallet.user
            )
            return {"share": share, "created": True}


@wallet_shares_router.get("/{wallet_id}")
async def api_get_wallet_shares(
    wallet_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> list[WalletShare]:
    """
    Get all shares for a wallet.
    Only the wallet owner can view shares.
    """
    # Verify this is the correct wallet
    if wallet.wallet.id != wallet_id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Admin key does not match wallet ID",
        )

    async with db.connect() as conn:
        shares = await get_wallet_shares(conn, wallet_id)

        # TODO: Populate usernames for display
        # Currently disabled due to get_account() hanging issue when called in a loop
        # for share in shares:
        #     account = await get_account(share.user_id)
        #     if account:
        #         share.username = account.username or account.email or share.user_id

        return shares


@wallet_shares_router.get("/shared/me")
async def api_get_my_shared_wallets(
    user: User = Depends(check_user_exists),
) -> list[WalletShare]:
    """
    Get all wallets shared with the current user.
    """
    async with db.connect() as conn:
        shares = await get_user_shared_wallets(conn, user.id)
        return shares


@wallet_shares_router.post("/accept/{share_id}")
async def api_accept_wallet_share(
    share_id: str,
    user: User = Depends(check_user_exists),
) -> WalletShare:
    """
    Accept a wallet share invitation.
    Only the user the wallet is shared with can accept it.
    Sets status='accepted'.
    """
    from ..models.wallet_shares import WalletShareStatus

    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        if share.user_id != user.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Only the recipient can accept this share",
            )

        if share.status != WalletShareStatus.PENDING:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Cannot accept share with status: {share.status}",
            )

        updated_share = await accept_wallet_share(conn, share_id)
        return updated_share


@wallet_shares_router.post("/decline/{share_id}")
async def api_decline_wallet_share(
    share_id: str,
    user: User = Depends(check_user_exists),
) -> dict:
    """
    Decline a wallet share invitation.
    Only the recipient can decline their own invitation.
    Sets status='rejected' so sender can see the rejection.
    """
    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        if share.user_id != user.id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Only the recipient can decline this share",
            )

        await reject_wallet_share(conn, share_id)
        return {"success": True, "message": "Share declined successfully"}


@wallet_shares_router.post("/leave/{wallet_id}")
async def api_leave_wallet_share(
    wallet_id: str,
    user: User = Depends(check_user_exists),
) -> dict:
    """
    Leave a shared wallet.
    Only the user who has accepted access to the shared wallet can leave it.
    Sets status='left' so owner can see the user left.
    """
    from ..models.wallet_shares import WalletShareStatus

    async with db.connect() as conn:
        # Verify the user has a share for this wallet
        shares = await get_wallet_shares(conn, wallet_id)
        user_share = next((s for s in shares if s.user_id == user.id), None)

        if not user_share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="You do not have access to this wallet",
            )

        if user_share.status != WalletShareStatus.ACCEPTED:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Cannot leave wallet with status: {user_share.status}",
            )

        await leave_wallet_share(conn, wallet_id, user.id)
        return {"success": True, "message": "Successfully left shared wallet"}


@wallet_shares_router.put("/{share_id}")
async def api_update_wallet_share_permissions(
    share_id: str,
    data: UpdateWalletSharePermissions,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> WalletShare:
    """
    Update permissions for a wallet share.
    Only the wallet owner can update shares using their admin key.
    """
    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        # Verify the admin key matches the wallet that owns this share
        if wallet.wallet.id != share.wallet_id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Admin key does not match share's wallet",
            )

        updated_share = await update_wallet_share_permissions(conn, share_id, data)
        return updated_share


@wallet_shares_router.delete("/{share_id}")
async def api_delete_wallet_share(
    share_id: str,
    wallet: WalletTypeInfo = Depends(require_admin_key),
) -> dict:
    """
    Revoke a wallet share (remove user's access).
    Only the wallet owner can revoke shares using their admin key.
    Sets status='revoked' so history is preserved.
    """
    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        # Verify the admin key matches the wallet that owns this share
        if wallet.wallet.id != share.wallet_id:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail="Admin key does not match share's wallet",
            )

        await revoke_wallet_share(conn, share_id)
        return {"success": True, "message": "Share revoked successfully"}
