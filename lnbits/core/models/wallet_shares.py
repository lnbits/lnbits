from __future__ import annotations

from datetime import datetime, timezone
from enum import IntFlag

from pydantic import BaseModel, Field


class WalletSharePermission(IntFlag):
    """Permission flags for shared wallets using bitmask"""

    VIEW = 1  # Can view balance and transactions
    CREATE_INVOICE = 2  # Can create invoices
    PAY_INVOICE = 4  # Can pay invoices
    MANAGE_SHARES = 8  # Can add/remove other users
    FULL_ACCESS = 15  # All permissions (1 + 2 + 4 + 8)


class WalletShare(BaseModel):
    id: str
    wallet_id: str
    user_id: str
    permissions: int
    shared_by: str
    shared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    accepted: bool = False
    accepted_at: datetime | None = None

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
