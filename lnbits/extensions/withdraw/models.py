from quart import url_for
from lnurl import Lnurl, LnurlWithdrawResponse, encode as lnurl_encode  # type: ignore
from sqlite3 import Row
from typing import NamedTuple
import shortuuid  # type: ignore


class WithdrawLink(NamedTuple):
    id: str
    wallet: str
    title: str
    min_withdrawable: int
    max_withdrawable: int
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
    def from_row(cls, row: Row) -> "WithdrawLink":
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
                "withdraw.api_lnurl_multi_response",
                unique_hash=self.unique_hash,
                id_unique_hash=multihash,
                _external=True,
            )
        else:
            url = url_for(
                "withdraw.api_lnurl_response",
                unique_hash=self.unique_hash,
                _external=True,
            )

        return lnurl_encode(url)

    @property
    def lnurl_response(self) -> LnurlWithdrawResponse:
        url = url_for(
            "withdraw.api_lnurl_callback", unique_hash=self.unique_hash, _external=True
        )
        return LnurlWithdrawResponse(
            callback=url,
            k1=self.k1,
            min_withdrawable=self.min_withdrawable * 1000,
            max_withdrawable=self.max_withdrawable * 1000,
            default_description=self.title,
        )


class HashCheck(NamedTuple):
    id: str
    lnurl_id: str

    @classmethod
    def from_row(cls, row: Row) -> "Hash":
        return cls(**dict(row))
