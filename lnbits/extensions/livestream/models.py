import json
from typing import Optional

from fastapi import Query
from lnurl import Lnurl
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from starlette.requests import Request


class CreateTrack(BaseModel):
    name: str = Query(...)
    download_url: str = Query(None)
    price_msat: int = Query(None, ge=0)
    producer_id: str = Query(None)
    producer_name: str = Query(None)


class Livestream(BaseModel):
    id: int
    wallet: str
    fee_pct: int
    current_track: Optional[int]

    def lnurl(self, request: Request) -> Lnurl:
        url = request.url_for("livestream.lnurl_livestream", ls_id=self.id)
        return lnurl_encode(url)


class Track(BaseModel):
    id: int
    download_url: Optional[str]
    price_msat: Optional[int]
    name: str
    producer: int

    @property
    def min_sendable(self) -> int:
        return min(100_000, self.price_msat or 100_000)

    @property
    def max_sendable(self) -> int:
        return max(50_000_000, self.price_msat * 5)

    def lnurl(self, request: Request) -> Lnurl:
        url = request.url_for("livestream.lnurl_track", track_id=self.id)
        return lnurl_encode(url)

    async def fullname(self) -> str:
        from .crud import get_producer

        producer = await get_producer(self.producer)
        if producer:
            producer_name = producer.name
        else:
            producer_name = "unknown author"

        return f"'{self.name}', from {producer_name}."

    async def lnurlpay_metadata(self) -> LnurlPayMetadata:
        description = (
            await self.fullname()
        ) + " Like this track? Send some sats in appreciation."

        if self.download_url:
            description += f" Send {round(self.price_msat/1000)} sats or more and you can download it."

        return LnurlPayMetadata(json.dumps([["text/plain", description]]))

    def success_action(
        self, payment_hash: str, request: Request
    ) -> Optional[LnurlPaySuccessAction]:
        if not self.download_url:
            return None

        url = request.url_for("livestream.track_redirect_download", track_id=self.id)
        url_with_query = f"{url}?p={payment_hash}"

        return UrlAction(
            url=url_with_query, description=f"Download the track {self.name}!"
        )


class Producer(BaseModel):
    id: int
    user: str
    wallet: str
    name: str
