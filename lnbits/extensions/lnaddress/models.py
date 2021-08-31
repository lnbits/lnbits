from typing import NamedTuple

class Domains(NamedTuple):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: str
    cost: int
    time: int

class Address(NamedTuple):
    id: str
    


# class Example(NamedTuple):
#    id: str
#    wallet: str
#
#    @classmethod
#    def from_row(cls, row: Row) -> "Example":
#        return cls(**dict(row))
