from __future__ import annotations

from datetime import datetime, timezone

from lnbits.db import Connection
from lnbits.helpers import urlsafe_short_hash

from ..models.wallet_shares import (
    CreateWalletShare,
    UpdateWalletSharePermissions,
    WalletShare,
    WalletSharePermission,
)


async def create_wallet_share(
    conn: Connection,
    wallet_id: str,
    data: CreateWalletShare,
    shared_by: str,
) -> WalletShare:
    """
    Create a new wallet share invitation.

    Args:
        conn: Database connection
        wallet_id: ID of wallet to share
        data: Share creation data (user_id, permissions)
        shared_by: User ID of the person sharing the wallet

    Returns:
        Created WalletShare object
    """
    share_id = urlsafe_short_hash()
    await conn.execute(
        """
        INSERT INTO wallet_shares
        (id, wallet_id, user_id, permissions, shared_by, shared_at)
        VALUES (:id, :wallet_id, :user_id, :permissions, :shared_by, :shared_at)
        """,
        {
            "id": share_id,
            "wallet_id": wallet_id,
            "user_id": data.user_id,
            "permissions": data.permissions,
            "shared_by": shared_by,
            "shared_at": datetime.now(timezone.utc),
        },
    )
    share = await get_wallet_share(conn, share_id)
    assert share, "Failed to create wallet share"
    return share


async def accept_wallet_share(
    conn: Connection,
    share_id: str,
) -> WalletShare:
    """
    Accept a pending wallet share invitation.

    Args:
        conn: Database connection
        share_id: ID of the share to accept

    Returns:
        Updated WalletShare object
    """
    await conn.execute(
        """
        UPDATE wallet_shares
        SET accepted = TRUE, accepted_at = :accepted_at
        WHERE id = :share_id
        """,
        {"accepted_at": datetime.now(timezone.utc), "share_id": share_id},
    )
    share = await get_wallet_share(conn, share_id)
    assert share, "Failed to accept wallet share"
    return share


async def get_wallet_share(
    conn: Connection,
    share_id: str,
) -> WalletShare | None:
    """
    Get a wallet share by ID.

    Args:
        conn: Database connection
        share_id: ID of the share

    Returns:
        WalletShare object or None if not found
    """
    row = await conn.fetchone(
        "SELECT * FROM wallet_shares WHERE id = :share_id",
        {"share_id": share_id},
    )
    return WalletShare(**row) if row else None


async def get_wallet_shares(
    conn: Connection,
    wallet_id: str,
) -> list[WalletShare]:
    """
    Get all shares for a specific wallet.

    Args:
        conn: Database connection
        wallet_id: ID of the wallet

    Returns:
        List of WalletShare objects
    """
    rows = await conn.fetchall(
        "SELECT * FROM wallet_shares WHERE wallet_id = :wallet_id ORDER BY shared_at DESC",
        {"wallet_id": wallet_id},
    )
    return [WalletShare(**row) for row in rows]


async def get_user_shared_wallets(
    conn: Connection,
    user_id: str,
) -> list[WalletShare]:
    """
    Get all wallets shared with a specific user.

    Args:
        conn: Database connection
        user_id: ID of the user

    Returns:
        List of WalletShare objects for wallets shared with this user
    """
    rows = await conn.fetchall(
        "SELECT * FROM wallet_shares WHERE user_id = :user_id ORDER BY shared_at DESC",
        {"user_id": user_id},
    )
    return [WalletShare(**row) for row in rows]


async def update_wallet_share_permissions(
    conn: Connection,
    share_id: str,
    data: UpdateWalletSharePermissions,
) -> WalletShare:
    """
    Update permissions for a wallet share.

    Args:
        conn: Database connection
        share_id: ID of the share to update
        data: New permissions data

    Returns:
        Updated WalletShare object
    """
    await conn.execute(
        "UPDATE wallet_shares SET permissions = :permissions WHERE id = :share_id",
        {"permissions": data.permissions, "share_id": share_id},
    )
    share = await get_wallet_share(conn, share_id)
    assert share, "Failed to update wallet share permissions"
    return share


async def delete_wallet_share(
    conn: Connection,
    share_id: str,
) -> None:
    """
    Delete a wallet share (remove user's access).

    Args:
        conn: Database connection
        share_id: ID of the share to delete
    """
    await conn.execute(
        "DELETE FROM wallet_shares WHERE id = :share_id",
        {"share_id": share_id},
    )


async def check_wallet_share_permission(
    conn: Connection,
    wallet_id: str,
    user_id: str,
    permission: WalletSharePermission,
) -> bool:
    """
    Check if a user has a specific permission on a wallet.

    Args:
        conn: Database connection
        wallet_id: ID of the wallet
        user_id: ID of the user
        permission: Permission flag to check

    Returns:
        True if user has the permission, False otherwise
    """
    row = await conn.fetchone(
        """
        SELECT permissions FROM wallet_shares
        WHERE wallet_id = :wallet_id AND user_id = :user_id AND accepted = TRUE
        """,
        {"wallet_id": wallet_id, "user_id": user_id},
    )
    if not row:
        return False

    permissions = row["permissions"]
    return bool(permissions & permission)


async def get_wallet_share_count(
    conn: Connection,
    wallet_id: str,
) -> int:
    """
    Get count of shares for a wallet.

    Args:
        conn: Database connection
        wallet_id: ID of the wallet

    Returns:
        Number of shares for this wallet
    """
    row = await conn.fetchone(
        "SELECT COUNT(*) as count FROM wallet_shares WHERE wallet_id = :wallet_id",
        {"wallet_id": wallet_id},
    )
    return row["count"] if row else 0
