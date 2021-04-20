import json
from quart import url_for
from typing import NamedTuple, Optional
from lnurl import Lnurl, encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore


class Livestream(NamedTuple):
    id: int
    wallet: str
    fee_pct: int
    current_track: Optional[int]

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("livestream.lnurl_livestream", ls_id=self.id, _external=True)
        return lnurl_encode(url)


class Track(NamedTuple):
    id: int
    download_url: str
    price_msat: int
    name: str
    producer: int

    @property
    def min_sendable(self) -> int:
        return min(100_000, self.price_msat or 100_000)

    @property
    def max_sendable(self) -> int:
        return max(50_000_000, self.price_msat * 5)

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("livestream.lnurl_track", track_id=self.id, _external=True)
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

    def success_action(self, payment_hash: str) -> Optional[LnurlPaySuccessAction]:
        if not self.download_url:
            return None

        return UrlAction(
            url=url_for(
                "livestream.track_redirect_download",
                track_id=self.id,
                p=payment_hash,
                _external=True,
            ),
            description=f"Download the track {self.name}!",
        )


class Producer(NamedTuple):
    id: int
    user: str
    wallet: str
    name: str
