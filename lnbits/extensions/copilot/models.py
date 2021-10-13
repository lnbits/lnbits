import json
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from starlette.requests import Request
from fastapi.param_functions import Query
from typing import Optional, Dict
from lnbits.lnurl import encode as lnurl_encode  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from sqlite3 import Row
from pydantic import BaseModel


class CreateCopilotData(BaseModel):
    id: Optional[str] = None
    user: Optional[str] = None
    title: Optional[str] = None
    lnurl_toggle: Optional[int] = None
    wallet: Optional[str] = None
    animation1: Optional[str] = None
    animation2: Optional[str] = None
    animation3: Optional[str] = None
    animation1threshold: Optional[int] = None
    animation2threshold: Optional[int] = None
    animation3threshold: Optional[int] = None
    animation1webhook: Optional[str] = None
    animation2webhook: Optional[str] = None
    animation3webhook: Optional[str] = None
    lnurl_title: Optional[str] = None
    show_message: Optional[int] = None
    show_ack: Optional[int] = None
    show_price: Optional[int] = None
    amount_made: Optional[int] = None
    timestamp: Optional[int] = None
    fullscreen_cam: Optional[int] = None
    iframe_url: Optional[int] = None
    success_url: Optional[str] = None


class Copilots(BaseModel):
    id: str
    user: str
    title: str
    lnurl_toggle: int
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
    show_price: int
    amount_made: int
    timestamp: int
    fullscreen_cam: int
    iframe_url: str

    @classmethod
    def from_row(cls, row: Row) -> "Copilots":
        return cls(**dict(row))

    def lnurl(self, req: Request) -> str:
        url = req.url_for("copilot.lnurl_response", link_id=self.id)
        return lnurl_encode(url)
