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


class satsdiceLink(BaseModel):
    id: str
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

    def lnurl(self, req: Request) -> Lnurl:
        return lnurl_encode(req.url_for("satsdice.lnurlp_response", item_id=self.id))

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def success_action(self, payment_hash: str, req: Request) -> Optional[Dict]:
        url = req.url_for(
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


class satsdicePayment(BaseModel):
    payment_hash: str
    satsdice_pay: str
    value: int
    paid: bool
    lost: bool


class satsdiceWithdraw(BaseModel):
    id: str
    satsdice_pay: str
    value: int
    unique_hash: str
    k1: str
    open_time: int
    used: int

    def lnurl(self, req: Request) -> Lnurl:
        return lnurl_encode(
            req.url_for(
                "satsdice.lnurlw_response",
                unique_hash=self.unique_hash,
                _external=True,
            )
        )

    @property
    def is_spent(self) -> bool:
        return self.used >= 1

    @property
    def lnurl_response(self, req: Request) -> LnurlWithdrawResponse:
        url = req.url_for(
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


class HashCheck(BaseModel):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Hash":
        return cls(**dict(row))


class CreateSatsDiceLink(BaseModel):
    wallet_id: str = Query(None)
    title: str = Query(None)
    base_url: str = Query(None)
    min_bet: str = Query(None)
    max_bet: str = Query(None)
    multiplier: int = Query(0)
    chance: float = Query(0)
    haircut: int = Query(0)


class CreateSatsDicePayment(BaseModel):
    satsdice_pay: str = Query(None)
    value: int = Query(0)
    payment_hash: str = Query(None)


class CreateSatsDiceWithdraw(BaseModel):
    payment_hash: str = Query(None)
    satsdice_pay: str = Query(None)
    value: int = Query(0)
    used: int = Query(0)


class CreateSatsDiceWithdraws(BaseModel):
    title: str = Query(None)
    min_satsdiceable: int = Query(0)
    max_satsdiceable: int = Query(0)
    uses: int = Query(0)
    wait_time: str = Query(None)
    is_unique: bool = Query(False)
