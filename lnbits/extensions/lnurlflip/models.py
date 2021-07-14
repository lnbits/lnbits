from quart import url_for
from lnurl import Lnurl, LnurllnurlflipResponse, encode as lnurl_encode  # type: ignore
from sqlite3 import Row
from typing import NamedTuple
import shortuuid  # type: ignore


class lnurlflipLink(NamedTuple):
    id: str
    wallet: str
    title: str
    min_lnurlflipable: int
    max_lnurlflipable: int
    uses: int
    wait_time: int
    is_unique: bool
    unique_hash: str
    k1: str
    open_time: int
    used: int
    usescsv: str
    number: int

    @classmethod
    def from_row(cls, row: Row) -> "lnurlflipLink":
        data = dict(row)
        data["is_unique"] = bool(data["is_unique"])
        data["number"] = 0
        return cls(**data)

    @property
    def is_spent(self) -> bool:
        return self.used >= self.uses

    @property
    def lnurl(self) -> Lnurl:
        if self.is_unique:
            usescssv = self.usescsv.split(",")
            tohash = self.id + self.unique_hash + usescssv[self.number]
            multihash = shortuuid.uuid(name=tohash)
            url = url_for(
                "lnurlflip.api_lnurl_multi_response",
                unique_hash=self.unique_hash,
                id_unique_hash=multihash,
                _external=True,
            )
        else:
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
            min_lnurlflipable=self.min_lnurlflipable * 1000,
            max_lnurlflipable=self.max_lnurlflipable * 1000,
            default_description=self.title,
        )


class HashCheck(NamedTuple):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Hash":
        return cls(**dict(row))
