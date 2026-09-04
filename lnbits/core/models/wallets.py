from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, validator

from lnbits.core.models.lnurl import StoredPayLinks
from lnbits.db import FilterModel
from lnbits.settings import settings
from lnbits.utils.exchange_rates import allowed_currencies

from .wallet_types import WalletType, wallet_type_capabilities


class WalletInfo(BaseModel):
    id: str
    name: str
    adminkey: str
    inkey: str
    balance_msat: int


class WalletPermission(Enum):
    VIEW_PAYMENTS = "view-payments"
    RECEIVE_PAYMENTS = "receive-payments"
    SEND_PAYMENTS = "send-payments"

    def __str__(self):
        return self.value


class WalletShareStatus(Enum):
    INVITE_SENT = "invite_sent"
    APPROVED = "approved"


class WalletSharePermission(BaseModel):
    # unique identifier for this share request
    request_id: str | None = None
    # username of the invited user
    username: str
    # ID of the wallet being shared with
    shared_with_wallet_id: str | None = None
    # permissions being granted
    permissions: list[WalletPermission] = []
    # status of the share request
    status: WalletShareStatus
    comment: str | None = None

    def approve(
        self,
        permissions: list[WalletPermission] | None = None,
        shared_with_wallet_id: str | None = None,
    ):
        self.status = WalletShareStatus.APPROVED
        if permissions is not None:
            self.permissions = permissions
        if shared_with_wallet_id is not None:
            self.shared_with_wallet_id = shared_with_wallet_id

    @property
    def is_approved(self) -> bool:
        return self.status == WalletShareStatus.APPROVED


class WalletExtra(BaseModel):
    icon: str = "flash_on"
    color: str = "primary"
    pinned: bool = False
    # What permissions this wallet grants when it's shared with other users
    shared_with: list[WalletSharePermission] = []

    def invite_user_to_shared_wallet(
        self,
        request_id: str,
        request_type: WalletShareStatus,
        username: str,
        permissions: list[WalletPermission] | None = None,
    ) -> WalletSharePermission:
        share = WalletSharePermission(
            request_id=request_id,
            username=username,
            status=request_type,
            permissions=permissions or [],
        )
        self.shared_with.append(share)
        return share

    def find_share_by_id(self, request_id: str) -> WalletSharePermission | None:
        for share in self.shared_with:
            if share.request_id == request_id:
                return share
        return None

    def find_share_for_wallet(
        self, shared_with_wallet_id: str
    ) -> WalletSharePermission | None:
        for share in self.shared_with:
            if share.shared_with_wallet_id == shared_with_wallet_id:
                return share
        return None

    def remove_share_by_id(self, request_id: str):
        self.shared_with = [
            share for share in self.shared_with if share.request_id != request_id
        ]


class BaseWallet(BaseModel):
    id: str
    user: str
    wallet_type: str = WalletType.LIGHTNING.value
    adminkey: str
    inkey: str


class Wallet(BaseWallet):
    name: str
    # Must be set only for shared wallets
    shared_wallet_id: str | None = None
    deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str | None = None
    lightning_address: str | None = None
    balance_msat: int = Field(default=0, no_database=True)
    extra: WalletExtra = WalletExtra()
    stored_paylinks: StoredPayLinks = StoredPayLinks()
    # What permission this wallet has when it's a shared wallet
    share_permissions: list[WalletPermission] = Field(default=[], no_database=True)

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_data()

    def mirror_shared_wallet(
        self,
        shared_wallet: Wallet,
    ):
        if not shared_wallet.is_lightning_wallet:
            return None

        self.wallet_type = WalletType.LIGHTNING_SHARED.value
        self.shared_wallet_id = shared_wallet.id
        self.name = shared_wallet.name
        self.share_permissions = shared_wallet.get_share_permissions(self.id)

        if len(self.share_permissions):
            self.currency = shared_wallet.currency
            self.lightning_address = shared_wallet.lightning_address
            self.balance_msat = shared_wallet.balance_msat

            self.stored_paylinks = shared_wallet.stored_paylinks
            self.extra.icon = shared_wallet.extra.icon
            self.extra.color = shared_wallet.extra.color

    def get_share_permissions(self, wallet_id: str) -> list[WalletPermission]:
        for share in self.extra.shared_with:
            if share.shared_with_wallet_id == wallet_id and share.is_approved:
                return share.permissions
        return []

    def has_permission(self, permission: WalletPermission) -> bool:
        capabilities = wallet_type_capabilities(self.type)
        if not self.is_lightning_shared_wallet:
            if permission == WalletPermission.VIEW_PAYMENTS:
                return True
            if permission == WalletPermission.RECEIVE_PAYMENTS:
                return capabilities.receives
            if permission == WalletPermission.SEND_PAYMENTS:
                return capabilities.sends
        if self.is_lightning_shared_wallet:
            return permission in self.share_permissions

        return False

    @property
    def source_wallet_id(self) -> str:
        """For shared wallets return the original wallet ID, else return own ID."""
        if self.is_lightning_shared_wallet and len(self.share_permissions):
            return self.shared_wallet_id or self.id
        return self.id

    @property
    def can_receive_payments(self) -> bool:
        return self.has_permission(WalletPermission.RECEIVE_PAYMENTS)

    @property
    def can_send_payments(self) -> bool:
        return self.has_permission(WalletPermission.SEND_PAYMENTS)

    @property
    def can_view_payments(self) -> bool:
        return self.has_permission(WalletPermission.VIEW_PAYMENTS)

    @property
    def balance(self) -> int:
        return int(self.balance_msat // 1000)

    @property
    def withdrawable_balance(self) -> int:
        return self.balance_msat - settings.fee_reserve(self.balance_msat)

    @property
    def is_lightning_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIGHTNING.value

    @property
    def is_lightning_shared_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIGHTNING_SHARED.value

    @property
    def is_fiat_wallet(self) -> bool:
        return self.wallet_type == WalletType.FIAT.value

    @property
    def is_onchain_wallet(self) -> bool:
        return self.wallet_type == WalletType.ONCHAIN.value

    @property
    def is_liquid_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIQUID.value

    @property
    def type(self) -> WalletType:
        return WalletType(self.wallet_type)

    def supports_payment_type(self, payment_type: WalletType) -> bool:
        if self.is_lightning_shared_wallet:
            return payment_type == WalletType.LIGHTNING
        return self.type == payment_type

    @property
    def can_be_shared(self) -> bool:
        return wallet_type_capabilities(self.type).shareable

    @property
    def supports_lightning_address(self) -> bool:
        return wallet_type_capabilities(self.type).lightning_address

    def _validate_data(self):
        if self.is_lightning_shared_wallet:
            if not self.shared_wallet_id:
                raise ValueError("Shared wallet ID must be set for shared wallets.")


class CreateWallet(BaseModel):
    name: str | None = None
    wallet_type: WalletType = WalletType.LIGHTNING
    shared_wallet_id: str | None = None
    currency: str | None = None

    @validator("currency")
    def validate_currency(cls, currency: str | None) -> str | None:
        if currency is None:
            return None
        currency = currency.upper()
        if currency not in allowed_currencies():
            raise ValueError("The provided currency is not supported")
        return currency


class KeyType(Enum):
    admin = 0
    invoice = 1
    invalid = 2

    # backwards compatibility
    def __eq__(self, other):
        return self.value == other


@dataclass
class WalletTypeInfo:
    key_type: KeyType
    wallet: Wallet


@dataclass
class BaseWalletTypeInfo:
    key_type: KeyType
    wallet: BaseWallet


class WalletsFilters(FilterModel):
    __search_fields__ = ["id", "name", "currency", "lightning_address"]

    __sort_fields__ = [
        "id",
        "name",
        "currency",
        "lightning_address",
        "created_at",
        "updated_at",
    ]

    id: str | None
    name: str | None
    currency: str | None
    lightning_address: str | None
