from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import Query
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from lnbits.db import FilterModel
from lnbits.helpers import is_valid_email_address, is_valid_pubkey, is_valid_username
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

    is_super_user: bool = Field(default=False, no_database=True)
    is_admin: bool = Field(default=False, no_database=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.is_super_user = settings.is_super_user(self.id)
        self.is_admin = settings.is_admin_user(self.id)

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

    def validate_fields(self):
        if self.username and not is_valid_username(self.username):
            raise ValueError("Invalid username.")
        if self.email and not is_valid_email_address(self.email):
            raise ValueError("Invalid email.")
        if self.pubkey and not is_valid_pubkey(self.pubkey):
            raise ValueError("Invalid pubkey.")
        user_uuid4 = UUID(hex=self.id, version=4)
        if user_uuid4.hex != self.id:
            raise ValueError("User ID is not valid UUID4 hex string.")


class AccountOverview(Account):
    transaction_count: Optional[int] = 0
    wallet_count: Optional[int] = 0
    balance_msat: Optional[int] = 0
    last_payment: Optional[datetime] = None


class AccountFilters(FilterModel):
    __search_fields__ = ["user", "email", "username", "pubkey", "wallet_id"]
    __sort_fields__ = [
        "balance_msat",
        "email",
        "username",
        "transaction_count",
        "wallet_count",
        "last_payment",
    ]

    email: Optional[str] = None
    user: Optional[str] = None
    username: Optional[str] = None
    pubkey: Optional[str] = None
    wallet_id: Optional[str] = None


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


class RegisterUser(BaseModel):
    email: Optional[str] = Query(default=None)
    username: str = Query(default=..., min_length=2, max_length=20)
    password: str = Query(default=..., min_length=8, max_length=50)
    password_repeat: str = Query(default=..., min_length=8, max_length=50)


class CreateUser(BaseModel):
    id: Optional[str] = Query(default=None)
    email: Optional[str] = Query(default=None)
    username: Optional[str] = Query(default=None, min_length=2, max_length=20)
    password: Optional[str] = Query(default=None, min_length=8, max_length=50)
    password_repeat: Optional[str] = Query(default=None, min_length=8, max_length=50)
    pubkey: str = Query(default=None, max_length=64)
    extensions: Optional[list[str]] = None
    extra: Optional[UserExtra] = None


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
