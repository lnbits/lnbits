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
    title: str
    min_bet: int
    max_bet: int
    amount: int
    served_meta: int
    served_pr: int
    multiplier: float
    haircut: float
    chance: float
    base_url: str
    open_time: int

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("satsdice.api_lnurlp_response", link_id=self.id, _external=True)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def success_action(self, payment_hash: str) -> Optional[Dict]:
        url = url_for(
            "satsdice.displaywin",
            link_id=self.id,
            payment_hash=payment_hash,
            _external=True,
        )
        #        url: ParseResult = urlparse(url)
        print(url)
        #        qs: Dict = parse_qs(url.query)
        #        qs["payment_hash"] = payment_hash
        #        url = url._replace(query=urlencode(qs, doseq=True))
        return {
            "tag": "url",
            "description": "Check the attached link",
            "url": url,
        }


class satsdicePayment(NamedTuple):
    payment_hash: str
    satsdice_pay: str
    value: int
    paid: bool
    lost: bool

    @classmethod
    def from_row(cls, row: Row) -> "satsdicePayment":
        data = dict(row)
        return cls(**data)


class satsdiceWithdraw(NamedTuple):
    id: str
    satsdice_pay: str
    value: int
    unique_hash: str
    k1: str
    open_time: int
    used: int

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceWithdraw":
        data = dict(row)
        return cls(**data)

    @property
    def is_spent(self) -> bool:
        return self.used >= 1

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
            minWithdrawable=self.value * 1000,
            maxWithdrawable=self.value * 1000,
            default_description="Satsdice winnings!",
        )


class HashCheck(NamedTuple):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Hash":
        return cls(**dict(row))
