import json
from sqlite3 import Row
from typing import Optional

from fastapi import Request
from lnurl import Lnurl
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from pydantic.main import BaseModel


class createLnurldevice(BaseModel):
    title: str
    wallet: str
    currency: str
    device: str
    profit: float
    amount: int
    pin: int
    profit1: float = 0
    amount1: int = 0
    pin1: int = 0
    profit2: float = 0
    amount2: int = 0
    pin2: int = 0
    profit3: float = 0
    amount3: int = 0
    pin3: int = 0
    profit4: float = 0
    amount4: int = 0
    pin4: int = 0


class lnurldevices(BaseModel):
    id: str
    key: str
    title: str
    wallet: str
    currency: str
    device: str
    profit: float
    amount: int
    pin: int
    profit1: float
    amount1: int
    pin1: int
    profit2: float
    amount2: int
    pin2: int
    profit3: float
    amount3: int
    pin3: int
    profit4: float
    amount4: int
    pin4: int
    timestamp: str

    def from_row(cls, row: Row) -> "lnurldevices":
        return cls(**dict(row))

    def lnurl(self, req: Request) -> Lnurl:
        url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
        return lnurl_encode(url)

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))


class lnurldevicepayment(BaseModel):
    id: str
    deviceid: str
    payhash: str
    payload: str
    pin: int
    sats: int
    timestamp: str

    @classmethod
    def from_row(cls, row: Row) -> "lnurldevicepayment":
        return cls(**dict(row))
