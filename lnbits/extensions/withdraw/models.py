import shortuuid
from fastapi import Query
from lnurl import Lnurl, LnurlWithdrawResponse
from lnurl import encode as lnurl_encode
from lnurl.models import ClearnetUrl, MilliSatoshi
from pydantic import BaseModel
from starlette.requests import Request


class CreateWithdrawData(BaseModel):
    title: str = Query(...)
    min_withdrawable: int = Query(..., ge=1)
    max_withdrawable: int = Query(..., ge=1)
    uses: int = Query(..., ge=1)
    wait_time: int = Query(..., ge=1)
    is_unique: bool
    webhook_url: str = Query(None)
    webhook_headers: str = Query(None)
    webhook_body: str = Query(None)
    custom_url: str = Query(None)


class WithdrawLink(BaseModel):
    id: str
    wallet: str = Query(None)
    title: str = Query(None)
    min_withdrawable: int = Query(0)
    max_withdrawable: int = Query(0)
    uses: int = Query(0)
    wait_time: int = Query(0)
    is_unique: bool = Query(False)
    unique_hash: str = Query(0)
    k1: str = Query(None)
    open_time: int = Query(0)
    used: int = Query(0)
    usescsv: str = Query(None)
    number: int = Query(0)
    webhook_url: str = Query(None)
    webhook_headers: str = Query(None)
    webhook_body: str = Query(None)
    custom_url: str = Query(None)

    @property
    def is_spent(self) -> bool:
        return self.used >= self.uses

    def lnurl(self, req: Request) -> Lnurl:
        if self.is_unique:
            usescssv = self.usescsv.split(",")
            tohash = self.id + self.unique_hash + usescssv[self.number]
            multihash = shortuuid.uuid(name=tohash)
            url = req.url_for(
                "withdraw.api_lnurl_multi_response",
                unique_hash=self.unique_hash,
                id_unique_hash=multihash,
            )
        else:
            url = req.url_for(
                "withdraw.api_lnurl_response", unique_hash=self.unique_hash
            )

        return lnurl_encode(url)

    def lnurl_response(self, req: Request) -> LnurlWithdrawResponse:
        url = req.url_for(
            name="withdraw.api_lnurl_callback", unique_hash=self.unique_hash
        )
        return LnurlWithdrawResponse(
            callback=ClearnetUrl(url, scheme="https"),
            k1=self.k1,
            minWithdrawable=MilliSatoshi(self.min_withdrawable * 1000),
            maxWithdrawable=MilliSatoshi(self.max_withdrawable * 1000),
            defaultDescription=self.title,
        )


class HashCheck(BaseModel):
    hash: bool
    lnurl: bool
