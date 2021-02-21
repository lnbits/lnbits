from typing import NamedTuple


class Domains(NamedTuple):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: str
    description: str
    cost: int
    amountmade: int
    time: int
    allowed_record_types: str


class Subdomains(NamedTuple):
    id: str
    wallet: str
    domain: str
    domain_name: str
    subdomain: str
    email: str
    ip: str
    sats: int
    duration: int
    paid: bool
    time: int
    record_type: str
