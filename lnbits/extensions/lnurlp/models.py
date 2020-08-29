import json
from flask import url_for
from lnurl import Lnurl, encode as lnurl_encode
from lnurl.types import LnurlPayMetadata
from sqlite3 import Row
from typing import NamedTuple

from lnbits.settings import FORCE_HTTPS


class PayLink(NamedTuple):
    id: str
    wallet: str
    description: str
    amount: int
    served_meta: int
    served_pr: int

    @classmethod
    def from_row(cls, row: Row) -> "PayLink":
        data = dict(row)
        return cls(**data)

    @property
    def lnurl(self) -> Lnurl:
        scheme = "https" if FORCE_HTTPS else None
        url = url_for("lnurlp.api_lnurl_response", link_id=self.id, _external=True, _scheme=scheme)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.description]]))
