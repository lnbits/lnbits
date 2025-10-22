from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from lnurl import encode as lnurl_encode
from pydantic import BaseModel, Field

from lnbits.core.models.lnurl import StoredPayLinks
from lnbits.db import FilterModel
from lnbits.helpers import url_for
from lnbits.settings import settings


class BaseWallet(BaseModel):
    id: str
    name: str
    adminkey: str
    inkey: str
    balance_msat: int


class WalletType(Enum):
    LIGHTNING = "lightning"
    LIGHTNING_SHARED = "lightning-shared"


class WalletPermission(Enum):
    VIEW_PAYMENTS = "view-payments"
    RECEIVE_PAYMENTS = "receive-payments"
    SEND_PAYMENTS = "send-payments"

    def __str__(self):
        return self.value


class WalletSharePermission(BaseModel):
    username: str | None
    wallet_id: str
    permissions: list[WalletPermission] = []
    approved: bool = False
    comment: str | None = None


class WalletExtra(BaseModel):
    icon: str = "flash_on"
    color: str = "primary"
    pinned: bool = False
    # What permissions this wallet grants when it's shared with other users
    shared_with: list[WalletSharePermission] = []
    # What permission this wallet has when it's a shared wallet
    granted_wallet_permission: list[WalletPermission] = []


class Wallet(BaseModel):
    id: str
    user: str
    name: str
    adminkey: str
    inkey: str
    wallet_type: str = WalletType.LIGHTNING.value
    # Must be set only for shared wallets
    shared_wallet_id: str | None = None
    deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str | None = None
    balance_msat: int = Field(default=0, no_database=True)
    extra: WalletExtra = WalletExtra()
    stored_paylinks: StoredPayLinks = StoredPayLinks()

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_data()

    def mirror_shared_wallet(
        self,
        shared_wallet: Wallet,
    ):
        if shared_wallet.wallet_type != WalletType.LIGHTNING.value:
            return None

        self.extra.granted_wallet_permission = shared_wallet.get_share_permission(
            self.id
        )
        self.wallet_type = WalletType.LIGHTNING_SHARED.value
        self.shared_wallet_id = shared_wallet.id
        self.currency = shared_wallet.currency
        self.balance_msat = shared_wallet.balance_msat

        self.stored_paylinks = shared_wallet.stored_paylinks
        self.extra.icon = shared_wallet.extra.icon
        self.extra.color = shared_wallet.extra.color

    def get_share_permission(self, wallet_id: str) -> list[WalletPermission]:
        for share in self.extra.shared_with:
            if share.wallet_id == wallet_id:
                return share.permissions
        return []

    @property
    def source_wallet_id(self) -> str:
        """For shared wallets return the original wallet ID, else return own ID."""
        if self.wallet_type == WalletType.LIGHTNING_SHARED.value:
            return self.shared_wallet_id or self.id
        return self.id

    @property
    def can_create_invoice(self) -> bool:
        if self.wallet_type == WalletType.LIGHTNING.value:
            return True
        if self.wallet_type == WalletType.LIGHTNING_SHARED.value:
            return (
                self.extra.granted_wallet_permission
                == WalletPermission.SEND_PAYMENTS.value
            )

        return False

    @property
    def can_pay_invoice(self) -> bool:
        if self.wallet_type == WalletType.LIGHTNING.value:
            return True
        if self.wallet_type == WalletType.LIGHTNING_SHARED.value:
            return (
                self.extra.granted_wallet_permission
                == WalletPermission.SEND_PAYMENTS.value
            )

        return False

    @property
    def balance(self) -> int:
        return int(self.balance_msat // 1000)

    @property
    def withdrawable_balance(self) -> int:
        return self.balance_msat - settings.fee_reserve(self.balance_msat)

    @property
    def lnurlwithdraw_full(self) -> str:
        url = url_for("/withdraw", external=True, usr=self.user, wal=self.id)
        try:
            return lnurl_encode(url)
        except Exception:
            return ""

    @property
    def is_lightning_shared_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIGHTNING_SHARED.value

    def _validate_data(self):
        if self.wallet_type == WalletType.LIGHTNING_SHARED.value:
            if not self.shared_wallet_id:
                raise ValueError("shared_wallet_id must be set for shared wallets")


class CreateWallet(BaseModel):
    name: str | None = None
    wallet_type: WalletType = WalletType.LIGHTNING
    shared_wallet_id: str | None = None


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


class WalletsFilters(FilterModel):
    __search_fields__ = ["id", "name", "currency"]

    __sort_fields__ = ["id", "name", "currency", "created_at", "updated_at"]

    id: str | None
    name: str | None
    currency: str | None
