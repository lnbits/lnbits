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


class WalletPermission(BaseModel):
    VIEW_ONLY = "view_only"
    RECEIVE_PAYMENTS = "receive_payments"
    SEND_PAYMENTS = "send_payments"
    ADMIN = "admin"


class WalletExtra(BaseModel):
    icon: str = "flash_on"
    color: str = "primary"
    pinned: bool = False
    shared_wallet_permission: WalletPermission | None = None


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

    def mirror_shared_wallet(
        self,
        shared_wallet: Wallet,
    ):
        if shared_wallet.wallet_type != WalletType.LIGHTNING.value:
            return None
        self.id = shared_wallet.id
        self.wallet_type = WalletType.LIGHTNING_SHARED.value
        self.shared_wallet_id = shared_wallet.id
        self.currency = shared_wallet.currency
        self.balance_msat = shared_wallet.balance_msat
        self.extra = shared_wallet.extra
        self.stored_paylinks = shared_wallet.stored_paylinks
        # todo: set permission from the original wallet
        # self.extra.shared_wallet_permission = permission

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


class CreateWallet(BaseModel):
    name: str | None = None


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
