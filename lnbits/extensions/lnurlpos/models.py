import json
from lnurl import Lnurl, LnurlWithdrawResponse, encode as lnurl_encode  # type: ignore
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from lnurl.types import LnurlPayMetadata  # type: ignore
from sqlite3 import Row
from typing import NamedTuple, Optional, Dict
import shortuuid  # type: ignore
from fastapi.param_functions import Query
from pydantic.main import BaseModel
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, Request


class createLnurlpos(BaseModel):
    title: str
    wallet: str
    currency: str


class lnurlposs(BaseModel):
    id: str
    key: str
    title: str
    wallet: str
    currency: str
    timestamp: str

    @classmethod
    def from_row(cls, row: Row) -> "lnurlposs":
        return cls(**dict(row))

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("lnurlpos.lnurl_response", pos_id=self.id, _external=True)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def success_action(self, paymentid: str, req: Request) -> Optional[Dict]:
        url = url_for(
            "lnurlpos.displaypin",
            paymentid=paymentid,
        )
        return {
            "tag": "url",
            "description": "Check the attached link",
            "url": url,
        }


class lnurlpospayment(BaseModel):
    id: str
    posid: str
    payhash: str
    payload: str
    pin: int
    sats: int
    timestamp: str

    @classmethod
    def from_row(cls, row: Row) -> "lnurlpospayment":
        return cls(**dict(row))
