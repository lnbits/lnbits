from hashlib import sha256
from typing import NamedTuple


class Paywall(NamedTuple):
    id: str
    wallet: str
    secret: str
    url: str
    memo: str
    amount: int
    time: int

    def key_for(self, fingerprint: str) -> str:
        return sha256(f"{self.secret}{fingerprint}".encode("utf-8")).hexdigest()
