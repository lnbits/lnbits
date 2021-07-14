from quart import url_for
from lnurl import Lnurl, LnurllnurlflipResponse, encode as lnurl_encode  # type: ignore
from sqlite3 import Row
from typing import NamedTuple
import shortuuid  # type: ignore


class lnurlflipWithdraw(NamedTuple):
    id: str
    wallet: str
    title: str
    value: int
    unique_hash: str
    k1: str
    odds: float
    open_time: int
    current_odds: float
    open_time: int

    @classmethod
    def from_row(cls, row: Row) -> "lnurlflipLink":
        data = dict(row)
        return cls(**data)

    @property
    def is_spent(self) -> bool:
        return self.used >= self.uses

    @property
    def lnurl(self) -> Lnurl:
        url = url_for(
            "lnurlflip.api_lnurl_response",
            unique_hash=self.unique_hash,
            _external=True,
        )

        return lnurl_encode(url)

    @property
    def lnurl_response(self) -> LnurllnurlflipResponse:
        url = url_for(
            "lnurlflip.api_lnurl_callback", unique_hash=self.unique_hash, _external=True
        )
        return LnurllnurlflipResponse(
            callback=url,
            k1=self.k1,
            min_lnurlflipable=self.value * 1000,
            max_lnurlflipable=self.value * 1000,
            default_description=self.title,
        )
