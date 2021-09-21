from sqlite3 import Row
import time
from quart import url_for
from lnurl import Lnurl, encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore
from typing import NamedTuple, Optional, Dict


class lnurlposs(NamedTuple):
    id: str
    secret: str
    title: str
    wallet: str
    message: str
    currency: str

    @classmethod
    def from_row(cls, row: Row) -> "lnurlposs":
        return cls(**dict(row))

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("lnurlpos.lnurl_response", pos_id=self.id, _external=True)
        return lnurl_encode(url)

    @property
    def lnurlpay_metadata(self) -> LnurlPayMetadata:
        return LnurlPayMetadata(json.dumps([["text/plain", self.title]]))

    def success_action(self, payment_hash: str) -> Optional[Dict]:
        url = url_for(
            "lnurlpos.displaypin",
            link_id=self.id,
            payment_hash=payment_hash,
            _external=True,
        )
        #        url: ParseResult = urlparse(url)
        print(url)
        #        qs: Dict = parse_qs(url.query)
        #        qs["payment_hash"] = payment_hash
        #        url = url._replace(query=urlencode(qs, doseq=True))
        return {
            "tag": "url",
            "description": "Check the attached link",
            "url": url,
        }
