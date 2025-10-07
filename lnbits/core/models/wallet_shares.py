from __future__ import annotations

from datetime import datetime, timezone
from enum import IntFlag, StrEnum

from pydantic import BaseModel, Field


class WalletSharePermission(IntFlag):
    """Permission flags for shared wallets using bitmask"""

    VIEW = 1  # Can view balance and transactions
    CREATE_INVOICE = 2  # Can create invoices
    PAY_INVOICE = 4  # Can pay invoices
    MANAGE_SHARES = 8  # Can add/remove other users
    FULL_ACCESS = 15  # All permissions (1 + 2 + 4 + 8)


class WalletShareStatus(StrEnum):
    """Status of a wallet share"""

    PENDING = "pending"  # Invitation sent, awaiting user response
    ACCEPTED = "accepted"  # User accepted the invitation (active share)
    REJECTED = "rejected"  # User declined the invitation before accepting
    REVOKED = "revoked"  # Owner revoked the share
    LEFT = "left"  # User left the share after accepting it


class WalletShare(BaseModel):
    id: str
    wallet_id: str
    user_id: str
    permissions: int
    shared_by: str
    shared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: WalletShareStatus = WalletShareStatus.PENDING
    status_updated_at: datetime | None = None  # When status last changed
    username: str | None = Field(default=None)  # Optional: populated by API for display
    wallet_name: str | None = Field(default=None)  # Optional: wallet name for display
    shared_by_username: str | None = Field(
        default=None
    )  # Optional: sharer username for display

    model_config: dict = {"extra": "allow"}  # Allow additional fields for flexibility

    @property
    def can_view(self) -> bool:
        """User can view balance and transactions"""
        return bool(self.permissions & WalletSharePermission.VIEW)

    @property
    def can_create_invoice(self) -> bool:
        """User can create invoices"""
        return bool(self.permissions & WalletSharePermission.CREATE_INVOICE)

    @property
    def can_pay_invoice(self) -> bool:
        """User can pay invoices"""
        return bool(self.permissions & WalletSharePermission.PAY_INVOICE)

    @property
    def can_manage_shares(self) -> bool:
        """User can manage sharing settings"""
        return bool(self.permissions & WalletSharePermission.MANAGE_SHARES)


class WalletShareResponse(BaseModel):
    """
    API response model for wallet shares.

    Security: Does NOT expose user_id to prevent potential account takeover
    if 'user-id-only' authentication is enabled. All operations should use
    share_id as the resource identifier.
    """

    id: str  # share_id - the resource identifier
    wallet_id: str
    permissions: int
    shared_by: str
    shared_at: datetime
    status: WalletShareStatus
    status_updated_at: datetime | None = None
    # Display fields only (no sensitive data)
    username: str | None = Field(default=None)
    wallet_name: str | None = Field(default=None)
    shared_by_username: str | None = Field(default=None)

    @property
    def can_view(self) -> bool:
        """User can view balance and transactions"""
        return bool(self.permissions & WalletSharePermission.VIEW)

    @property
    def can_create_invoice(self) -> bool:
        """User can create invoices"""
        return bool(self.permissions & WalletSharePermission.CREATE_INVOICE)

    @property
    def can_pay_invoice(self) -> bool:
        """User can pay invoices"""
        return bool(self.permissions & WalletSharePermission.PAY_INVOICE)

    @property
    def can_manage_shares(self) -> bool:
        """User can manage sharing settings"""
        return bool(self.permissions & WalletSharePermission.MANAGE_SHARES)


class CreateWalletShare(BaseModel):
    user_id: str
    permissions: int = WalletSharePermission.VIEW


class UpdateWalletSharePermissions(BaseModel):
    permissions: int
