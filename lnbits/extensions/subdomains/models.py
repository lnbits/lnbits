from fastapi.params import Query
from pydantic.main import BaseModel


class CreateDomain(BaseModel):
    wallet: str = Query(...)  # type: ignore
    domain: str = Query(...)  # type: ignore
    cf_token: str = Query(...)  # type: ignore
    cf_zone_id: str = Query(...)  # type: ignore
    webhook: str = Query("")  # type: ignore
    description: str = Query(..., min_length=0)  # type: ignore
    cost: int = Query(..., ge=0)  # type: ignore
    allowed_record_types: str = Query(...)  # type: ignore


class CreateSubdomain(BaseModel):
    domain: str = Query(...)  # type: ignore
    subdomain: str = Query(...)  # type: ignore
    email: str = Query(...)  # type: ignore
    ip: str = Query(...)  # type: ignore
    sats: int = Query(..., ge=0)  # type: ignore
    duration: int = Query(...)  # type: ignore
    record_type: str = Query(...)  # type: ignore


class Domains(BaseModel):
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


class Subdomains(BaseModel):
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
