from time import time
from typing import Annotated

from lnurl import LnAddress, Lnurl, LnurlPayResponse
from lnurl.exceptions import LnAddressError
from pydantic import BaseModel, Field, ValidateAs

LightningAddress = Annotated[
    LnAddress, ValidateAs(str, lambda value: _validate_lightning_address(value))
]


class CreateLnurlPayment(BaseModel):
    res: LnurlPayResponse | None = None
    lnurl: Lnurl | LightningAddress | None = None
    amount: int
    comment: str | None = None
    unit: str | None = None
    internal_memo: str | None = None


class CreateLnurlWithdraw(BaseModel):
    lnurl_w: Lnurl


class LnurlScan(BaseModel):
    lnurl: Lnurl | LightningAddress


class StoredPayLink(BaseModel):
    lnurl: str
    label: str
    last_used: int = Field(default_factory=lambda: int(time()))


class StoredPayLinks(BaseModel):
    links: list[StoredPayLink] = []


def _validate_lightning_address(value: str) -> LnAddress:
    try:
        return LnAddress(value)
    except LnAddressError as exc:
        raise ValueError("Invalid Lightning address.") from exc
