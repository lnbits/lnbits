from time import time

from lnurl import LnAddress, Lnurl, LnurlPayResponse
from pydantic import BaseModel, Field


class CreateLnurlPayment(BaseModel):
    res: LnurlPayResponse | None = None
    lnurl: Lnurl | LnAddress | None = None
    amount: int
    comment: str | None = None
    unit: str | None = None
    internal_memo: str | None = None


class CreateLnurlWithdraw(BaseModel):
    lnurl_w: Lnurl


class LnurlScan(BaseModel):
    lnurl: Lnurl | LnAddress


class StoredPayLink(BaseModel):
    lnurl: str
    label: str
    last_used: int = Field(default_factory=lambda: int(time()))


class StoredPayLinks(BaseModel):
    links: list[StoredPayLink] = []
