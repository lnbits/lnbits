import json
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from starlette.requests import Request
from fastapi.param_functions import Query
from typing import Optional, Dict
from lnbits.lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from sqlite3 import Row
from pydantic import BaseModel

class CreatePayLinkData(BaseModel):
    description:  str
    min:  int = Query(0.01, ge=0.01)
    max:  int = Query(0.01, ge=0.01)
    currency:  str = Query(None)
    comment_chars:  int = Query(0, ge=0, lt=800)
    webhook_url:  str = Query(None)
    success_text:  str = Query(None)
    success_url:  str = Query(None)

class PayLink(BaseModel):
    id: int
    wallet: str
    description: str
    min: int
    served_meta: int
    served_pr: int
    webhook_url: Optional[str]
    success_text: Optional[str]
    success_url: Optional[str]
    currency: Optional[str]
    comment_chars: int
    max: int

    @classmethod
    def from_row(cls, row: Row) -> "PayLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurl(self) -> str:
        r = Request
        url = r.url_for("lnurlp.api_lnurl_response", link_id=self.id, _external=True)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.description]]))

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
            return {
                "tag": "message",
                "message": self.success_text,
            }
        else:
            return None
