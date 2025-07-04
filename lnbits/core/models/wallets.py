from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ecdsa import SECP256k1, SigningKey
from pydantic import BaseModel, Field

from lnbits.db import FilterModel
from lnbits.helpers import url_for
from lnbits.lnurl import encode as lnurl_encode
from lnbits.settings import settings


class BaseWallet(BaseModel):
    id: str
    name: str
    adminkey: str
    inkey: str
    balance_msat: int


class WalletExtra(BaseModel):
    icon: str = "flash_on"
    color: str = "primary"
    pinned: bool = False


class Wallet(BaseModel):
    id: str
    user: str
    name: str
    adminkey: str
    inkey: str
    deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    currency: str | None = None
    balance_msat: int = Field(default=0, no_database=True)
    extra: WalletExtra = WalletExtra()

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

    def lnurlauth_key(self, domain: str) -> SigningKey:
        hashing_key = hashlib.sha256(self.id.encode()).digest()
        linking_key = hmac.digest(hashing_key, domain.encode(), "sha256")

        return SigningKey.from_string(
            linking_key, curve=SECP256k1, hashfunc=hashlib.sha256
        )


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
