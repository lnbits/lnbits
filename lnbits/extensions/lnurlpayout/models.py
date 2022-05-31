from sqlite3 import Row

from pydantic import BaseModel


class CreateLnurlPayoutData(BaseModel):
    title: str
    lnurlpay: str
    threshold: int


class lnurlpayout(BaseModel):
    id: str
    title: str
    wallet: str
    admin_key: str
    lnurlpay: str
    threshold: int
