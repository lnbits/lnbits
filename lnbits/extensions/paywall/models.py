from typing import NamedTuple


class Paywall(NamedTuple):
    id: str
    wallet: str
    url: str
    memo: str
    amount: int
    time: int
