from flask import url_for
from lnurl import Lnurl, LnurlWithdrawResponse, encode as lnurl_encode
from os import getenv
from typing import NamedTuple


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

    @property
    def is_spent(self) -> bool:
        return self.used >= self.uses

    @property
    def is_onion(self) -> bool:
        return getenv("LNBITS_WITH_ONION", 1) == 1

    @property
    def lnurl(self) -> Lnurl:
        scheme = None if self.is_onion else "https"
        url = url_for("withdraw.api_lnurl_response", unique_hash=self.unique_hash, _external=True, _scheme=scheme)
        return lnurl_encode(url)

    @property
    def lnurl_response(self) -> LnurlWithdrawResponse:
        scheme = None if self.is_onion else "https"
        url = url_for("withdraw.api_lnurl_callback", unique_hash=self.unique_hash, _external=True, _scheme=scheme)

        return LnurlWithdrawResponse(
            callback=url,
            k1=self.k1,
            min_withdrawable=self.min_withdrawable * 1000,
            max_withdrawable=self.max_withdrawable * 1000,
            default_description="LNbits LNURL withdraw",
        )
