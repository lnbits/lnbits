import json
from quart import url_for
from lnurl import Lnurl, LnurlWithdrawResponse, encode as lnurl_encode  # type: ignore
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from lnurl.types import LnurlPayMetadata  # type: ignore
from sqlite3 import Row
from typing import NamedTuple, Optional, Dict
import shortuuid  # type: ignore


class satsdiceLink(NamedTuple):
    id: int
    wallet: str
    description: str
    min: int
    served_meta: int
    served_pr: int
    webhook_url: str
    success_text: str
    success_url: str
    currency: str
    comment_chars: int
    max: int

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("lnurlp.api_lnurl_response", link_id=self.id, _external=True)
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


class satsdiceWithdraw(NamedTuple):
    id: str
    wallet: str
    title: str
    value: int
    unique_hash: str
    k1: str
    odds: float
    actual_odds: float
    open_time: int
    current_odds: float
    open_time: int

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceWithdraw":
        data = dict(row)
        return cls(**data)

    @property
    def is_spent(self) -> bool:
        return self.used >= self.uses

    @property
    def lnurl(self) -> Lnurl:
        url = url_for(
            "satsdice.api_lnurlw_response",
            unique_hash=self.unique_hash,
            _external=True,
        )

        return lnurl_encode(url)

    @property
    def lnurl_response(self) -> LnurlWithdrawResponse:
        url = url_for(
            "satsdice.api_lnurlw_callback",
            unique_hash=self.unique_hash,
            _external=True,
        )
        return LnurlWithdrawResponse(
            callback=url,
            k1=self.k1,
            min_satsdiceable=self.value * 1000,
            max_satsdiceable=self.value * 1000,
            default_description=self.title,
        )

class HashCheck(NamedTuple):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Hash":
        return cls(**dict(row))
