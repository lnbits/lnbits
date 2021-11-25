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

    def from_row(cls, row: Row) -> "lnurlposs":
        return cls(**dict(row))

    def lnurl(self, req: Request) -> Lnurl:
        url = req.url_for("lnurlpos.lnurl_response", pos_id=self.id, _external=True)
        return lnurl_encode(url)

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def success_action(
        self, paymentid: str, req: Request
    ) -> Optional[LnurlPaySuccessAction]:

        return UrlAction(
            url=req.url_for("lnurlpos.displaypin", paymentid=paymentid),
            description="Check the attached link",
        )


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
