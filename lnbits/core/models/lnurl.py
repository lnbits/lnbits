from time import time

# TODO something is wrong about LnAddress
from lnurl import Lnurl, LnurlPayResponse
from pydantic import BaseModel, Field


# Warning: Mixing V1 and V2 models is not supported. `LnurlPayResponse` is a V2 model.
class CreateLnurlPayment(BaseModel):
    res: LnurlPayResponse | None = None
    lnurl: Lnurl | None = None
    amount: int
    comment: str | None = None
    unit: str | None = None
    internal_memo: str | None = None


class CreateLnurlWithdraw(BaseModel):
    lnurl_w: Lnurl


class LnurlScan(BaseModel):
    lnurl: Lnurl


class StoredPayLink(BaseModel):
    lnurl: str
    label: str
    last_used: int = Field(default_factory=lambda: int(time()))


class StoredPayLinks(BaseModel):
    links: list[StoredPayLink] = []
