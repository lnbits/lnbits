from sqlite3 import Row
from typing import NamedTuple
import time

from lnurl import Lnurl, encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore

class Copilots(NamedTuple):
    id: str
    user: str
    title: str
    wallet: str
    animation1: str
    animation2: str
    animation3: str
    animation1threshold: int
    animation2threshold: int
    animation3threshold: int
    animation1webhook: str
    animation2webhook: str
    animation3webhook: str
    lnurl_title: str
    show_message: int
    show_ack: int
    amount_made: int
    timestamp: int
    fullscreen_cam: int
    iframe_url: str
    notes: str

    @classmethod
    def from_row(cls, row: Row) -> "Copilots":
        return cls(**dict(row))

    @property
    def lnurl(self) -> Lnurl:
        url = url_for("copilots.lnurl_response", ls_id=self.id, _external=True)
        return lnurl_encode(url)