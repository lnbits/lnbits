from typing import NamedTuple


class Forms(NamedTuple):
    id: str
    wallet: str
    name: str
    description: str
    costpword: int
    amountmade: int
    time: int


class Tickets(NamedTuple):
    id: str
    form: str
    email: str
    ltext: str
    name: str
    wallet: str
    sats: int
    paid: bool
    time: int

