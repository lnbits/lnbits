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
    balance_msat: int

    @property
    def balance(self) -> int:
        return int(self.balance / 1000)

    def get_payment(self, payhash: str) -> "Payment":
        from .crud import get_wallet_payment

        return get_wallet_payment(self.id, payhash)

    def get_payments(self, *, include_all_pending: bool = False) -> List["Payment"]:
        from .crud import get_wallet_payments

        return get_wallet_payments(self.id, include_all_pending=include_all_pending)


class Payment(NamedTuple):
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
    def is_in(self) -> bool:
        return self.amount > 0

    @property
    def is_out(self) -> bool:
        return self.amount < 0

    def set_pending(self, pending: bool) -> None:
        from .crud import update_payment_status

        update_payment_status(self.payhash, pending)

    def delete(self) -> None:
        from .crud import delete_payment

        delete_payment(self.payhash)
