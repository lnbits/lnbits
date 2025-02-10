from typing import Optional

from pydantic import BaseModel


class CreateLnurl(BaseModel):
    description_hash: str
    callback: str
    amount: int
    comment: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None


class CreateLnurlAuth(BaseModel):
    callback: str


class PayLnurlWData(BaseModel):
    lnurl_w: str
