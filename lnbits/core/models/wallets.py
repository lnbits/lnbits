from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, validator

from lnbits.core.models.lnurl import StoredPayLinks
from lnbits.db import FilterModel
from lnbits.settings import settings


class WalletInfo(BaseModel):
    id: str
    name: str
    adminkey: str
    inkey: str
    balance_msat: int


class WalletType(Enum):
    LIGHTNING = "lightning"
    FIAT = "fiat"
    ONCHAIN = "onchain"
    LIGHTNING_SHARED = "lightning-shared"


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
    onchain_network: Literal["Mainnet", "Testnet", "Testnet4"] | None = None
    balance_msat: int = Field(default=0, no_database=True)
    extra: WalletExtra = WalletExtra()
    stored_paylinks: StoredPayLinks = StoredPayLinks()
    # What permission this wallet has when it's a shared wallet
    share_permissions: list[WalletPermission] = Field(default=[], no_database=True)

    def __init__(self, **data):
        super().__init__(**data)
        self._validate_data()

    def copy_with_keys(self, keep: bool = True) -> Wallet:
        """Return a wallet copy, masking its credentials when keep is False."""
        wallet = self.copy()
        if not keep:
            wallet.adminkey = "*" * 32
            wallet.inkey = "*" * 32
        return wallet

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
        if self.is_onchain_wallet:
            return permission == WalletPermission.VIEW_PAYMENTS
        if self.wallet_type == WalletType.FIAT.value:
            return permission in (
                WalletPermission.VIEW_PAYMENTS,
                WalletPermission.RECEIVE_PAYMENTS,
            )
        if self.is_lightning_wallet:
            return True
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
        if self.wallet_type in (WalletType.FIAT.value, WalletType.ONCHAIN.value):
            return 0
        return self.balance_msat - settings.fee_reserve(self.balance_msat)

    @property
    def is_onchain_wallet(self) -> bool:
        return self.wallet_type == WalletType.ONCHAIN.value

    @property
    def is_lightning_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIGHTNING.value

    @property
    def is_lightning_shared_wallet(self) -> bool:
        return self.wallet_type == WalletType.LIGHTNING_SHARED.value

    def _validate_data(self):
        if self.is_lightning_shared_wallet:
            if not self.shared_wallet_id:
                raise ValueError("Shared wallet ID must be set for shared wallets.")


class CreateWallet(BaseModel):
    onchain_network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"
    name: str | None = None
    wallet_type: WalletType = WalletType.LIGHTNING
    shared_wallet_id: str | None = None
    currency: str | None = None


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


class OnchainMeta(BaseModel):
    masterpub: str = ""
    fingerprint: str = ""
    script_type: str | None = None
    accountPath: str = ""  # noqa: N815 - preserve the stored JSON key
    xpub: str | None = None
    sync_checked_at: int = 0
    sync_error: str | None = None


class OnchainConfig(BaseModel):
    explorer_provider: Literal["auto", "lnbits", "mempool"] = "auto"
    mempool_endpoint: str = "https://mempool.space"
    receive_gap_limit: int = Field(default=20, ge=1, le=1000)
    change_gap_limit: int = Field(default=5, ge=1, le=1000)
    sats_denominated: bool = True

    @validator("mempool_endpoint")
    @classmethod
    def valid_endpoint(cls, value):
        url = urlsplit(value)
        if (
            url.scheme not in ("https", "http")
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "Enter an HTTP(S) explorer URL without credentials or query"
            )
        return value.rstrip("/")


class OnchainWallet(Wallet):
    wallet_type: str = WalletType.ONCHAIN.value
    onchain_meta: OnchainMeta = Field(default_factory=OnchainMeta)
    onchain_config: OnchainConfig = Field(default_factory=OnchainConfig)
    onchain_wallet_kind: Literal["watch", "hot"] | None = None
    onchain_address_no: int = -1
    onchain_backup_confirmed: bool = False


class CreateOnchainWalletMeta(BaseModel):
    accountPath: str = ""  # noqa: N815 - preserve the API field name
    xpub: str | None = None


class CreateOnchainWallet(BaseModel):
    masterpub: str = Field(..., min_length=1, max_length=10000)
    title: str = Field(..., min_length=1, max_length=100)
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"
    meta: CreateOnchainWalletMeta = Field(default_factory=CreateOnchainWalletMeta)


class OnchainWalletConfigResponse(OnchainConfig):
    network: Literal["Mainnet", "Testnet", "Testnet4"] = "Mainnet"
    lnbits_explorer_network: str | None = None
    explorer_url: str
