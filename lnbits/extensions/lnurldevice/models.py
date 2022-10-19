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


class lnurldevices(BaseModel):
    id: str
    key: str
    title: str
    wallet: str
    currency: str
    device: str
    profit: float
    amount: int
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
