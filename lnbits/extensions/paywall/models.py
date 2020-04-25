from typing import NamedTuple


class Paywall(NamedTuple):
    id: str
    wallet: str
    secret: str
    url: str
    memo: str
    amount: int
    time: int
