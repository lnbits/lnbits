from typing import NamedTuple


class Domains(NamedTuple):
    id: str
    wallet: str
    domainName: str
    cfToken: str
    cfZoneId: str
    webhook: str
    description: str
    cost: int
    amountmade: int
    time: int


class Subdomains(NamedTuple):
    id: str
    domainName: str
    email: str
    subdomain: str
    ip: str
    wallet: str
    sats: int
    paid: bool
    time: int
