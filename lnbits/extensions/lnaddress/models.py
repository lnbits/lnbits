import json
from typing import Optional

from fastapi import Query
from lnurl.types import LnurlPayMetadata
from pydantic import BaseModel


class CreateDomain(BaseModel):
    wallet: str = Query(...)
    domain: str = Query(...)
    cf_token: str = Query(...)
    cf_zone_id: str = Query(...)
    webhook: str = Query(None)
    cost: int = Query(..., ge=0)


class Domains(BaseModel):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: Optional[str]
    cost: int
    time: int


class CreateAddress(BaseModel):
    domain: str = Query(...)
    username: str = Query(...)
    email: str = Query(None)
    wallet_endpoint: str = Query(...)
    wallet_key: str = Query(...)
    sats: int = Query(..., ge=0)
    duration: int = Query(..., ge=1)


class Addresses(BaseModel):
    id: str
    wallet: str
    domain: str
    email: Optional[str]
    username: str
    wallet_key: str
    wallet_endpoint: str
    sats: int
    duration: int
    paid: bool
    time: int

    async def lnurlpay_metadata(self, domain) -> LnurlPayMetadata:
        text = f"Payment to {self.username}"
        identifier = f"{self.username}@{domain}"
        metadata = [["text/plain", text], ["text/identifier", identifier]]

        return LnurlPayMetadata(json.dumps(metadata))
