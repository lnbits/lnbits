import json
import hmac
import hashlib
from quart import url_for
from ecdsa import SECP256k1, SigningKey  # type: ignore
from lnurl import encode as lnurl_encode  # type: ignore
from typing import List, NamedTuple, Optional, Dict
from sqlite3 import Row

from lnbits.settings import WALLET


class User(NamedTuple):
    id: str
    email: str
    extensions: List[str] = []
    wallets: List["Wallet"] = []
    password: Optional[str] = None

    @property
    def wallet_ids(self) -> List[str]:
        return [wallet.id for wallet in self.wallets]

    def get_wallet(self, wallet_id: str) -> Optional["Wallet"]:
        w = [wallet for wallet in self.wallets if wallet.id == wallet_id]
        return w[0] if w else None


class Wallet(NamedTuple):
    id: str
    name: str
    user: str
    adminkey: str
    inkey: str
    balance_msat: int

    @property
    def balance(self) -> int:
        return self.balance_msat // 1000

    @property
    def withdrawable_balance(self) -> int:
        from .services import fee_reserve

        return self.balance_msat - fee_reserve(self.balance_msat)

    @property
    def lnurlwithdraw_full(self) -> str:
        url = url_for(
            "core.lnurl_full_withdraw",
            usr=self.user,
            wal=self.id,
            _external=True,
        )
        try:
            return lnurl_encode(url)
        except:
            return ""

    def lnurlauth_key(self, domain: str) -> SigningKey:
        hashing_key = hashlib.sha256(self.id.encode("utf-8")).digest()
        linking_key = hmac.digest(hashing_key, domain.encode("utf-8"), "sha256")

        return SigningKey.from_string(
            linking_key,
            curve=SECP256k1,
            hashfunc=hashlib.sha256,
        )

    async def get_payment(self, payment_hash: str) -> Optional["Payment"]:
        from .crud import get_wallet_payment

        return await get_wallet_payment(self.id, payment_hash)

    async def get_payments(
        self,
        *,
        complete: bool = True,
        pending: bool = False,
        outgoing: bool = True,
        incoming: bool = True,
        exclude_uncheckable: bool = False,
    ) -> List["Payment"]:
        from .crud import get_payments

        return await get_payments(
            wallet_id=self.id,
            complete=complete,
            pending=pending,
            outgoing=outgoing,
            incoming=incoming,
            exclude_uncheckable=exclude_uncheckable,
        )


class Payment(NamedTuple):
    checking_id: str
    pending: bool
    amount: int
    fee: int
    memo: str
    time: int
    bolt11: str
    preimage: str
    payment_hash: str
    extra: Dict
    wallet_id: str
    webhook: str
    webhook_status: int

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
            wallet_id=row["wallet"],
            webhook=row["webhook"],
            webhook_status=row["webhook_status"],
        )

    @property
    def tag(self) -> Optional[str]:
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
    def is_uncheckable(self) -> bool:
        return self.checking_id.startswith("temp_") or self.checking_id.startswith(
            "internal_"
        )

    async def set_pending(self, pending: bool) -> None:
        from .crud import update_payment_status

        await update_payment_status(self.checking_id, pending)

    async def check_pending(self) -> None:
        if self.is_uncheckable:
            return

        if self.is_out:
            status = await WALLET.get_payment_status(self.checking_id)
        else:
            status = await WALLET.get_invoice_status(self.checking_id)

        if self.is_out and status.failed:
            print(f" - deleting outgoing failed payment {self.checking_id}: {status}")
            await self.delete()
        elif not status.pending:
            print(
                f" - marking '{'in' if self.is_in else 'out'}' {self.checking_id} as not pending anymore: {status}"
            )
            await self.set_pending(status.pending)

    async def delete(self) -> None:
        from .crud import delete_payment

        await delete_payment(self.checking_id)


class BalanceCheck(NamedTuple):
    wallet: str
    service: str
    url: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(wallet=row["wallet"], service=row["service"], url=row["url"])
