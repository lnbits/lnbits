from http import HTTPStatus

from fastapi import APIRouter, Depends, HTTPException

from lnbits.core.db import db
from lnbits.core.crud import get_account
from lnbits.core.crud.wallets import get_wallet
from lnbits.core.models import User
from lnbits.core.models.wallet_shares import (
    CreateWalletShare,
    UpdateWalletSharePermissions,
    WalletShare,
    WalletSharePermission,
)
from lnbits.decorators import check_user_exists

from ..crud.wallet_shares import (
    accept_wallet_share,
    create_wallet_share,
    delete_wallet_share,
    get_user_shared_wallets,
    get_wallet_share,
    get_wallet_shares,
    update_wallet_share_permissions,
)

wallet_shares_router = APIRouter(prefix="/api/v1/wallet_shares", tags=["Wallet Shares"])


@wallet_shares_router.post("/{wallet_id}")
async def api_create_wallet_share(
    wallet_id: str,
    data: CreateWalletShare,
    user: User = Depends(check_user_exists),
) -> WalletShare:
    """
    Share a wallet with another user.
    Only the wallet owner can share their wallet.
    """
    # Verify wallet exists and user owns it
    wallet = await get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    if wallet.user != user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Only wallet owner can share the wallet",
        )

    # Don't allow sharing with self
    if data.user_id == user.id:
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
                conn, existing_share.id, UpdateWalletSharePermissions(permissions=share_data.permissions)
            )
            return updated_share
        else:
            # Create new share
            share = await create_wallet_share(conn, wallet_id, share_data, user.id)
            return share


@wallet_shares_router.get("/{wallet_id}")
async def api_get_wallet_shares(
    wallet_id: str,
    user: User = Depends(check_user_exists),
) -> list[WalletShare]:
    """
    Get all shares for a wallet.
    Only the wallet owner can view shares.
    """
    # Verify wallet exists and user owns it
    wallet = await get_wallet(wallet_id)
    if not wallet:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found")

    if wallet.user != user.id:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail="Only wallet owner can view shares",
        )

    async with db.connect() as conn:
        shares = await get_wallet_shares(conn, wallet_id)
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


@wallet_shares_router.put("/{share_id}")
async def api_update_wallet_share_permissions(
    share_id: str,
    data: UpdateWalletSharePermissions,
    user: User = Depends(check_user_exists),
) -> WalletShare:
    """
    Update permissions for a wallet share.
    Only the wallet owner or users with MANAGE_SHARES permission can update.
    """
    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        # Check if user is wallet owner
        wallet = await get_wallet(share.wallet_id)
        if not wallet:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found"
            )

        is_owner = wallet.user == user.id

        # If not owner, check if user has MANAGE_SHARES permission
        if not is_owner:
            from ..crud.wallet_shares import check_wallet_share_permission

            has_permission = await check_wallet_share_permission(
                conn, share.wallet_id, user.id, WalletSharePermission.MANAGE_SHARES
            )
            if not has_permission:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="Only wallet owner or users with MANAGE_SHARES permission can update permissions",
                )

        updated_share = await update_wallet_share_permissions(conn, share_id, data)
        return updated_share


@wallet_shares_router.delete("/{share_id}")
async def api_delete_wallet_share(
    share_id: str,
    user: User = Depends(check_user_exists),
) -> dict:
    """
    Delete a wallet share (revoke access).
    Only the wallet owner or users with MANAGE_SHARES permission can delete shares.
    Users can also delete their own received shares.
    """
    async with db.connect() as conn:
        share = await get_wallet_share(conn, share_id)
        if not share:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Share not found"
            )

        # Check if user is wallet owner
        wallet = await get_wallet(share.wallet_id)
        if not wallet:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, detail="Wallet not found"
            )

        is_owner = wallet.user == user.id
        is_recipient = share.user_id == user.id

        # If not owner or recipient, check if user has MANAGE_SHARES permission
        if not is_owner and not is_recipient:
            from ..crud.wallet_shares import check_wallet_share_permission

            has_permission = await check_wallet_share_permission(
                conn, share.wallet_id, user.id, WalletSharePermission.MANAGE_SHARES
            )
            if not has_permission:
                raise HTTPException(
                    status_code=HTTPStatus.FORBIDDEN,
                    detail="Only wallet owner, recipient, or users with MANAGE_SHARES permission can delete shares",
                )

        await delete_wallet_share(conn, share_id)
        return {"success": True, "message": "Share deleted successfully"}
