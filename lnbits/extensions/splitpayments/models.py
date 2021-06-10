from typing import NamedTuple


class Target(NamedTuple):
    wallet: str
    source: str
    percent: int
    alias: str
