import json
from typing import List, NamedTuple, Optional, Dict
from sqlite3 import Row


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

    def get_payment(self, payment_hash: str) -> Optional["Payment"]:
        from .crud import get_wallet_payment

        return get_wallet_payment(self.id, payment_hash)

    def get_payments(
        self,
        *,
        complete: bool = True,
        pending: bool = False,
        outgoing: bool = True,
        incoming: bool = True,
        exclude_uncheckable: bool = False
    ) -> List["Payment"]:
        from .crud import get_wallet_payments

        return get_wallet_payments(
            self.id,
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
        return self.checking_id.startswith("temp_") or self.checking_id.startswith("internal_")

    def set_pending(self, pending: bool) -> None:
        from .crud import update_payment_status

        update_payment_status(self.checking_id, pending)

    def delete(self) -> None:
        from .crud import delete_payment

        delete_payment(self.checking_id)
