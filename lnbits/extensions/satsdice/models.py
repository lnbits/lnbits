import json
from sqlite3 import Row
from typing import Dict, Optional

from fastapi import Request
from fastapi.param_functions import Query
from lnurl import Lnurl
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from pydantic.main import BaseModel


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

    def lnurl(self, req: Request) -> str:
        return lnurl_encode(req.url_for("satsdice.lnurlp_response", link_id=self.id))

    @classmethod
    def from_row(cls, row: Row) -> "satsdiceLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(
            json.dumps(
                [
                    [
                        "text/plain",
                        f"{self.title} (Chance: {self.chance}%, Multiplier: {self.multiplier})",
                    ]
                ]
            )
        )

    def success_action(self, payment_hash: str, req: Request) -> Optional[Dict]:
        url = req.url_for(
            "satsdice.displaywin", link_id=self.id, payment_hash=payment_hash
        )
        return {"tag": "url", "description": "Check the attached link", "url": url}


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
            req.url_for("satsdice.lnurlw_response", unique_hash=self.unique_hash)
        )

    @property
    def is_spent(self) -> bool:
        return self.used >= 1

    def lnurl_response(self, req: Request):
        url = req.url_for("satsdice.api_lnurlw_callback", unique_hash=self.unique_hash)
        withdrawResponse = {
            "tag": "withdrawRequest",
            "callback": url,
            "k1": self.k1,
            "minWithdrawable": self.value * 1000,
            "maxWithdrawable": self.value * 1000,
            "defaultDescription": "Satsdice winnings!",
        }
        return withdrawResponse


class HashCheck(BaseModel):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row):
        return cls(**dict(row))


class CreateSatsDiceLink(BaseModel):
    wallet: str = Query(None)
    title: str = Query(None)
    base_url: str = Query(None)
    min_bet: str = Query(None)
    max_bet: str = Query(None)
    multiplier: float = Query(0)
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
