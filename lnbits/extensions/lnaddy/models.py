import json
from sqlite3 import Row
from typing import Dict, Optional
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

from fastapi.param_functions import Query
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from starlette.requests import Request

from lnbits.lnurl import encode as lnurl_encode  # type: ignore


class CreatePayLinkData(BaseModel):
    description: str
    min: float = Query(1, ge=0.01)
    max: float = Query(1, ge=0.01)
    currency: str = Query(None)
    comment_chars: int = Query(0, ge=0, lt=800)
    webhook_url: str = Query(None)
    webhook_headers: str = Query(None)
    webhook_body: str = Query(None)
    success_text: str = Query(None)
    success_url: str = Query(None)
    fiat_base_multiplier: int = Query(100, ge=1)
    lnaddress: str


class PayLink(BaseModel):
    id: int
    wallet: str
    wallet_key: str
    description: str
    min: float
    served_meta: int
    served_pr: int
    webhook_url: Optional[str]
    webhook_headers: Optional[str]
    webhook_body: Optional[str]
    success_text: Optional[str]
    success_url: Optional[str]
    currency: Optional[str]
    comment_chars: int
    max: float
    fiat_base_multiplier: int
    lnaddress: str

    @classmethod
    def from_row(cls, row: Row) -> "PayLink":
        data = dict(row)
        if data["currency"] and data["fiat_base_multiplier"]:
            data["min"] /= data["fiat_base_multiplier"]
            data["max"] /= data["fiat_base_multiplier"]
        return cls(**data)

    def lnurl(self, req: Request) -> str:
        url = req.url_for("lnaddy.api_lnurl_response", link_id=self.id)
        return lnurl_encode(url)

    def success_action(self, payment_hash: str) -> Optional[Dict]:
        if self.success_url:
            url: ParseResult = urlparse(self.success_url)
            qs: Dict = parse_qs(url.query)
            qs["payment_hash"] = payment_hash
            url = url._replace(query=urlencode(qs, doseq=True))
            return {
                "tag": "url",
                "description": self.success_text or "~",
                "url": urlunparse(url),
            }
        elif self.success_text:
            return {"tag": "message", "message": self.success_text}
        else:
            return None

    async def lnurlpay_metadata(self, domain) -> LnurlPayMetadata:
        text = f"Payment to {self.lnaddress}"
        identifier = f"{self.lnaddress}@{domain}"
        metadata = [["text/plain", text], ["text/identifier", identifier]]

        return LnurlPayMetadata(json.dumps(metadata))
