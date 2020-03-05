from decimal import Decimal
from typing import List, NamedTuple, Optional


class User(NamedTuple):
    id: str
    email: str
    extensions: Optional[List[str]] = []
    wallets: Optional[List["Wallet"]] = []
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
    balance: Decimal

    def get_transaction(self, payhash: str) -> "Transaction":
        from .crud import get_wallet_transaction

        return get_wallet_transaction(self.id, payhash)

    def get_transactions(self) -> List["Transaction"]:
        from .crud import get_wallet_transactions

        return get_wallet_transactions(self.id)


class Transaction(NamedTuple):
    payhash: str
    pending: bool
    amount: int
    fee: int
    memo: str
    time: int

    @property
    def msat(self) -> int:
        return self.amount

    @property
    def sat(self) -> int:
        return self.amount / 1000

    @property
    def tx_type(self) -> str:
        return "payment" if self.amount < 0 else "invoice"

    def set_pending(self, pending: bool) -> None:
        from .crud import update_transaction_status

        update_transaction_status(self.payhash, pending)
