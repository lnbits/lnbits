from typing import NamedTuple
import json
from lnurl.types import LnurlPayMetadata  # type: ignore

class Domains(NamedTuple):
    id: str
    wallet: str
    domain: str
    cf_token: str
    cf_zone_id: str
    webhook: str
    cost: int
    time: int

class Addresses(NamedTuple):
    id: str
    wallet: str
    domain: str
    email: str
    username: str
    wallet_key: str
    wallet_endpoint: str
    sats: int
    duration: int
    paid: bool
    time: int

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        text = f"Payment to {self.username}"
        metadata = [["text/plain", text]]

        return LnurlPayMetadata(json.dumps(metadata))
