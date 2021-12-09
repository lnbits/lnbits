from sqlite3 import Row

from pydantic import BaseModel

class CreateLnurlPayoutData(BaseModel):
    lnurlpay: str
    threshold: int

class lnurlpayout(BaseModel):
    id: str
    title: str
    wallet: str
    lnurlpay: str
    threshold: str
