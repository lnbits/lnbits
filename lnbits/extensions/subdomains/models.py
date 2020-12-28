from typing import NamedTuple


class Domains(NamedTuple):
    id: str
    wallet: str
    domain: str
    cfToken: str
    cfZoneId: str
    webhook: str
    description: str
    cost: int
    amountmade: int
    time: int


class Subdomains(NamedTuple):
    id: str
    wallet: str
    domain: str
    subdomain: str
    email: str
    ip: str
    sats: int
    paid: bool
    time: int
