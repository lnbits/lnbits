from datetime import datetime, timezone
from typing import Optional

from lnurl import LnAddress, Lnurl, LnurlPayResponse
from pydantic import BaseModel, Field


class CreateLnurlPayment(BaseModel):
    res: LnurlPayResponse | None = None
    lnurl: Lnurl | LnAddress | None = None
    amount: int
    comment: Optional[str] = None
    unit: Optional[str] = None
    internal_memo: Optional[str] = None


class CreateLnurlWithdraw(BaseModel):
    lnurl_w: Lnurl


class LnurlScan(BaseModel):
    lnurl: Lnurl | LnAddress


class StoredPayLink(BaseModel):
    lnurl: Lnurl | LnAddress
    label: str
    last_used: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
