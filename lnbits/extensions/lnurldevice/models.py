import json
from sqlite3 import Row
from typing import List, Optional

from fastapi import Request
from lnurl import encode as lnurl_encode
from lnurl.types import LnurlPayMetadata
from pydantic import BaseModel


class createLnurldevice(BaseModel):
    title: str
    wallet: str
    currency: str
    device: str
    profit: float = 0
    amount: Optional[int] = 0
    pin: int = 0
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

    @classmethod
    def from_row(cls, row: Row) -> "lnurldevices":
        return cls(**dict(row))

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def switches(self, req: Request) -> List:
        switches = []
        if self.profit > 0:
            url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
            switches.append(
                [
                    str(self.pin),
                    str(self.profit),
                    str(self.amount),
                    lnurl_encode(
                        url
                        + "?gpio="
                        + str(self.pin)
                        + "&profit="
                        + str(self.profit)
                        + "&amount="
                        + str(self.amount)
                    ),
                ]
            )
        if self.profit1 > 0:
            url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
            switches.append(
                [
                    str(self.pin1),
                    str(self.profit1),
                    str(self.amount1),
                    lnurl_encode(
                        url
                        + "?gpio="
                        + str(self.pin1)
                        + "&profit="
                        + str(self.profit1)
                        + "&amount="
                        + str(self.amount1)
                    ),
                ]
            )
        if self.profit2 > 0:
            url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
            switches.append(
                [
                    str(self.pin2),
                    str(self.profit2),
                    str(self.amount2),
                    lnurl_encode(
                        url
                        + "?gpio="
                        + str(self.pin2)
                        + "&profit="
                        + str(self.profit2)
                        + "&amount="
                        + str(self.amount2)
                    ),
                ]
            )
        if self.profit3 > 0:
            url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
            switches.append(
                [
                    str(self.pin3),
                    str(self.profit3),
                    str(self.amount3),
                    lnurl_encode(
                        url
                        + "?gpio="
                        + str(self.pin3)
                        + "&profit="
                        + str(self.profit3)
                        + "&amount="
                        + str(self.amount3)
                    ),
                ]
            )
        if self.profit4 > 0:
            url = req.url_for("lnurldevice.lnurl_v1_params", device_id=self.id)
            switches.append(
                [
                    str(self.pin4),
                    str(self.profit4),
                    str(self.amount4),
                    lnurl_encode(
                        url
                        + "?gpio="
                        + str(self.pin4)
                        + "&profit="
                        + str(self.profit4)
                        + "&amount="
                        + str(self.amount4)
                    ),
                ]
            )
        return switches


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
