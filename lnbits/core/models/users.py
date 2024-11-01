from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import Query
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from lnbits.db import FilterModel
from lnbits.settings import settings

from .wallets import Wallet


class UserExtra(BaseModel):
    email_verified: Optional[bool] = False
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    picture: Optional[str] = None
    # Auth provider, possible values:
    # - "env": the user was created automatically by the system
    # - "lnbits": the user was created via register form (username/pass or user_id only)
    # - "google | github | ...": the user was created using an SSO provider
    provider: Optional[str] = "lnbits"  # auth provider


class Account(BaseModel):
    id: str
    username: Optional[str] = None
    password_hash: Optional[str] = None
    pubkey: Optional[str] = None
    email: Optional[str] = None
    extra: UserExtra = UserExtra()
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_super_user(self) -> bool:
        return self.id == settings.super_user

    @property
    def is_admin(self) -> bool:
        return self.id in settings.lnbits_admin_users or self.is_super_user

    def hash_password(self, password: str) -> str:
        """sets and returns the hashed password"""
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.password_hash = pwd_context.hash(password)
        return self.password_hash

    def verify_password(self, password: str) -> bool:
        """returns True if the password matches the hash"""
        if not self.password_hash:
            return False
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        return pwd_context.verify(password, self.password_hash)


class AccountOverview(Account):
    transaction_count: Optional[int] = 0
    wallet_count: Optional[int] = 0
    balance_msat: Optional[int] = 0
    last_payment: Optional[datetime] = None


class AccountFilters(FilterModel):
    __search_fields__ = ["id", "email", "username"]
    __sort_fields__ = [
        "balance_msat",
        "email",
        "username",
        "transaction_count",
        "wallet_count",
        "last_payment",
    ]

    id: str
    last_payment: Optional[datetime] = None
    transaction_count: Optional[int] = None
    wallet_count: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None


class User(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    email: Optional[str] = None
    username: Optional[str] = None
    pubkey: Optional[str] = None
    extensions: list[str] = []
    wallets: list[Wallet] = []
    admin: bool = False
    super_user: bool = False
    has_password: bool = False
    extra: UserExtra = UserExtra()

    @property
    def wallet_ids(self) -> list[str]:
        return [wallet.id for wallet in self.wallets]

    def get_wallet(self, wallet_id: str) -> Optional[Wallet]:
        w = [wallet for wallet in self.wallets if wallet.id == wallet_id]
        return w[0] if w else None

    @classmethod
    def is_extension_for_user(cls, ext: str, user: str) -> bool:
        if ext not in settings.lnbits_admin_extensions:
            return True
        if user == settings.super_user:
            return True
        if user in settings.lnbits_admin_users:
            return True
        return False


class CreateUser(BaseModel):
    email: Optional[str] = Query(default=None)
    username: str = Query(default=..., min_length=2, max_length=20)
    password: str = Query(default=..., min_length=8, max_length=50)
    password_repeat: str = Query(default=..., min_length=8, max_length=50)


class UpdateUser(BaseModel):
    user_id: str
    email: Optional[str] = Query(default=None)
    username: Optional[str] = Query(default=..., min_length=2, max_length=20)
    extra: Optional[UserExtra] = None


class UpdateUserPassword(BaseModel):
    user_id: str
    password_old: Optional[str] = None
    password: str = Query(default=..., min_length=8, max_length=50)
    password_repeat: str = Query(default=..., min_length=8, max_length=50)
    username: str = Query(default=..., min_length=2, max_length=20)


class UpdateUserPubkey(BaseModel):
    user_id: str
    pubkey: str = Query(default=..., max_length=64)


class ResetUserPassword(BaseModel):
    reset_key: str
    password: str = Query(default=..., min_length=8, max_length=50)
    password_repeat: str = Query(default=..., min_length=8, max_length=50)


class UpdateSuperuserPassword(BaseModel):
    username: str = Query(default=..., min_length=2, max_length=20)
    password: str = Query(default=..., min_length=8, max_length=50)
    password_repeat: str = Query(default=..., min_length=8, max_length=50)


class LoginUsr(BaseModel):
    usr: str


class LoginUsernamePassword(BaseModel):
    username: str
    password: str


class AccessTokenPayload(BaseModel):
    sub: str
    usr: Optional[str] = None
    email: Optional[str] = None
    auth_time: Optional[int] = 0


class CreateTopup(BaseModel):
    id: str
    amount: int
