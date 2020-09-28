import json
from quart import url_for
from lnurl import Lnurl, encode as lnurl_encode
from lnurl.types import LnurlPayMetadata
from sqlite3 import Row
from typing import NamedTuple


class PayLink(NamedTuple):
    id: int
    wallet: str
    description: str
    amount: int
    served_meta: int
    served_pr: int
    webhook_url: str
    success_text: str
    success_url: str

    @classmethod
    def from_row(cls, row: Row) -> "PayLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("lnurlp.api_lnurl_response", link_id=self.id, _external=True)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.description]]))


class Invoice(NamedTuple):
    payment_hash: str
    link_id: int
    webhook_sent: bool
