import datetime
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import Enum
from sqlite3 import Row
from typing import Callable, Dict, List, Optional

from ecdsa import SECP256k1, SigningKey
from fastapi import Query
from lnurl import encode as lnurl_encode
from loguru import logger
from pydantic import BaseModel

from lnbits.db import Connection, FilterModel, FromRowModel
from lnbits.helpers import url_for
from lnbits.settings import settings
from lnbits.wallets import get_wallet_class
from lnbits.wallets.base import PaymentStatus


class Wallet(BaseModel):
    id: str
    name: str
    user: str
    adminkey: str
    inkey: str
    currency: Optional[str]
    balance_msat: int
    deleted: bool

    @property
    def balance(self) -> int:
        return self.balance_msat // 1000

    @property
    def withdrawable_balance(self) -> int:
        from .services import fee_reserve

        return self.balance_msat - fee_reserve(self.balance_msat)

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

    async def get_payment(self, payment_hash: str) -> Optional["Payment"]:
        from .crud import get_standalone_payment

        return await get_standalone_payment(payment_hash)


class WalletType(Enum):
    admin = 0
    invoice = 1
    invalid = 2

    # backwards compatibility
    def __eq__(self, other):
        return self.value == other


@dataclass
class WalletTypeInfo:
    wallet_type: WalletType
    wallet: Wallet


class User(BaseModel):
    id: str
    email: Optional[str] = None
    extensions: List[str] = []
    wallets: List[Wallet] = []
    password: Optional[str] = None
    admin: bool = False
    super_user: bool = False

    @property
    def wallet_ids(self) -> List[str]:
        return [wallet.id for wallet in self.wallets]

    def get_wallet(self, wallet_id: str) -> Optional["Wallet"]:
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


class Payment(FromRowModel):
    checking_id: str
    pending: bool
    amount: int
    fee: int
    memo: Optional[str]
    time: int
    bolt11: str
    preimage: str
    payment_hash: str
    expiry: Optional[float]
    extra: Dict = {}
    wallet_id: str
    webhook: Optional[str]
    webhook_status: Optional[int]

    @classmethod
    def from_row(cls, row: Row):
        return cls(
            checking_id=row["checking_id"],
            payment_hash=row["hash"] or "0" * 64,
            bolt11=row["bolt11"] or "",
            preimage=row["preimage"] or "0" * 64,
            extra=json.loads(row["extra"] or "{}"),
            pending=row["pending"],
            amount=row["amount"],
            fee=row["fee"],
            memo=row["memo"],
            time=row["time"],
            expiry=row["expiry"],
            wallet_id=row["wallet"],
            webhook=row["webhook"],
            webhook_status=row["webhook_status"],
        )

    @property
    def tag(self) -> Optional[str]:
        if self.extra is None:
            return ""
        return self.extra.get("tag")

    @property
    def msat(self) -> int:
        return self.amount

    @property
    def sat(self) -> int:
        return self.amount // 1000

    @property
    def is_in(self) -> bool:
        return self.amount > 0

    @property
    def is_out(self) -> bool:
        return self.amount < 0

    @property
    def is_expired(self) -> bool:
        return self.expiry < time.time() if self.expiry else False

    @property
    def is_uncheckable(self) -> bool:
        return self.checking_id.startswith("internal_")

    async def update_status(
        self,
        status: PaymentStatus,
        conn: Optional[Connection] = None,
    ) -> None:
        from .crud import update_payment_details

        await update_payment_details(
            checking_id=self.checking_id,
            pending=status.pending,
            fee=status.fee_msat,
            preimage=status.preimage,
            conn=conn,
        )

    async def set_pending(self, pending: bool) -> None:
        from .crud import update_payment_status

        self.pending = pending

        await update_payment_status(self.checking_id, pending)

    async def check_status(
        self,
        conn: Optional[Connection] = None,
    ) -> PaymentStatus:
        if self.is_uncheckable:
            return PaymentStatus(None)

        logger.debug(
            f"Checking {'outgoing' if self.is_out else 'incoming'} "
            f"pending payment {self.checking_id}"
        )

        WALLET = get_wallet_class()
        if self.is_out:
            status = await WALLET.get_payment_status(self.checking_id)
        else:
            status = await WALLET.get_invoice_status(self.checking_id)

        logger.debug(f"Status: {status}")

        if self.is_in and status.pending and self.is_expired and self.expiry:
            expiration_date = datetime.datetime.fromtimestamp(self.expiry)
            logger.debug(
                f"Deleting expired incoming pending payment {self.checking_id}: "
                f"expired {expiration_date}"
            )
            await self.delete(conn)
        # wait at least 15 minutes before deleting failed outgoing payments
        elif self.is_out and status.failed:
            if self.time + 900 < int(time.time()):
                logger.warning(
                    f"Deleting outgoing failed payment {self.checking_id}: {status}"
                )
                await self.delete(conn)
            else:
                logger.warning(
                    f"Tried to delete outgoing payment {self.checking_id}: "
                    "skipping because it's not old enough"
                )
        elif not status.pending:
            logger.info(
                f"Marking '{'in' if self.is_in else 'out'}' "
                f"{self.checking_id} as not pending anymore: {status}"
            )
            await self.update_status(status, conn=conn)
        return status

    async def delete(self, conn: Optional[Connection] = None) -> None:
        from .crud import delete_wallet_payment

        await delete_wallet_payment(self.checking_id, self.wallet_id, conn=conn)


class PaymentFilters(FilterModel):
    __search_fields__ = ["memo", "amount"]

    checking_id: str
    amount: int
    fee: int
    memo: Optional[str]
    time: datetime.datetime
    bolt11: str
    preimage: str
    payment_hash: str
    expiry: Optional[datetime.datetime]
    extra: Dict = {}
    wallet_id: str
    webhook: Optional[str]
    webhook_status: Optional[int]


class PaymentHistoryPoint(BaseModel):
    date: datetime.datetime
    income: int
    spending: int
    balance: int


class BalanceCheck(BaseModel):
    wallet: str
    service: str
    url: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(wallet=row["wallet"], service=row["service"], url=row["url"])


def _do_nothing(*_):
    pass


class CoreAppExtra:
    register_new_ext_routes: Callable = _do_nothing
    register_new_ratelimiter: Callable


class TinyURL(BaseModel):
    id: str
    url: str
    endless: bool
    wallet: str
    time: float

    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))


class ConversionData(BaseModel):
    from_: str = "sat"
    amount: float
    to: str = "usd"


class Callback(BaseModel):
    callback: str


class DecodePayment(BaseModel):
    data: str


class CreateLnurl(BaseModel):
    description_hash: str
    callback: str
    amount: int
    comment: Optional[str] = None
    description: Optional[str] = None


class CreateInvoice(BaseModel):
    unit: str = "sat"
    internal: bool = False
    out: bool = True
    amount: float = Query(None, ge=0)
    memo: Optional[str] = None
    description_hash: Optional[str] = None
    unhashed_description: Optional[str] = None
    expiry: Optional[int] = None
    lnurl_callback: Optional[str] = None
    lnurl_balance_check: Optional[str] = None
    extra: Optional[dict] = None
    webhook: Optional[str] = None
    bolt11: Optional[str] = None


class CreateTopup(BaseModel):
    id: str
    amount: int


class CreateLnurlAuth(BaseModel):
    callback: str


class CreateWallet(BaseModel):
    name: Optional[str] = None


class CreateWebPushSubscription(BaseModel):
    subscription: str


class WebPushSubscription(BaseModel):
    endpoint: str
    user: str
    data: str
    host: str
    timestamp: str
