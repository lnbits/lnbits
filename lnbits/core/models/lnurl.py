from typing import Optional

from lnurl import LnurlPayResponse
from pydantic import BaseModel


class CreateLnurlPayment(BaseModel):
    res: LnurlPayResponse
    amount: int
    comment: Optional[str] = None
    unit: Optional[str] = None
    internal_memo: Optional[str] = None


class CreateLnurlWithdraw(BaseModel):
    lnurl_w: str
