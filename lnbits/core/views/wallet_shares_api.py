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
    delete_wallet_share,
    get_user_shared_wallets,
    get_wallet_share,
    get_wallet_shares,
    leave_wallet_share,
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
) -> WalletShare:
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

    # Don't allow sharing with self
    if data.user_id == wallet.wallet.user:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Cannot share wallet with yourself",
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

    # Use the actual user ID from the account, not the input (which might be username)
    share_data = CreateWalletShare(user_id=recipient.id, permissions=data.permissions)

    async with db.connect() as conn:
        # Check if wallet is already shared with this user
        from ..crud.wallet_shares import get_wallet_shares

        existing_shares = await get_wallet_shares(conn, wallet_id)
        existing_share = next(
            (s for s in existing_shares if s.user_id == recipient.id), None
        )

        if existing_share:
            # Update permissions on existing share
            from ..crud.wallet_shares import update_wallet_share_permissions

            updated_share = await update_wallet_share_permissions(
                conn,
                existing_share.id,
                UpdateWalletSharePermissions(permissions=share_data.permissions),
            )
            return updated_share
        else:
            # Create new share
            share = await create_wallet_share(
                conn, wallet_id, share_data, wallet.wallet.user
            )
            return share


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
                detail="Only the recipient can accept this share",
            )

        if share.accepted:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Share already accepted"
            )

        updated_share = await accept_wallet_share(conn, share_id)
        return updated_share


@wallet_shares_router.post("/leave/{wallet_id}")
async def api_leave_wallet_share(
    wallet_id: str,
    user: User = Depends(check_user_exists),
) -> dict:
    """
    Leave a shared wallet.
    Only the user who has access to the shared wallet can leave it.
    """
    async with db.connect() as conn:
        # Verify the user has a share for this wallet
        shares = await get_wallet_shares(conn, wallet_id)
        user_share = next((s for s in shares if s.user_id == user.id), None)

        if not user_share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail="You do not have access to this wallet",
            )

        if user_share.left_at:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="You have already left this wallet",
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
    Delete a wallet share (revoke access).
    Only the wallet owner can delete shares using their admin key.
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

        await delete_wallet_share(conn, share_id)
        return {"success": True, "message": "Share deleted successfully"}
