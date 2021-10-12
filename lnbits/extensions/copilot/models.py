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
    id: str = Query(None)
    user: str = Query(None)
    title: str = Query(None)
    lnurl_toggle: int = Query(None)
    wallet: str = Query(None)
    animation1: str = Query(None)
    animation2: str = Query(None)
    animation3: str = Query(None)
    animation1threshold: int = Query(None)
    animation2threshold: int = Query(None)
    animation3threshold: int = Query(None)
    animation1webhook: str = Query(None)
    animation2webhook: str = Query(None)
    animation3webhook: str = Query(None)
    lnurl_title: str = Query(None)
    show_message: int = Query(None)
    show_ack: int = Query(None)
    show_price: int = Query(None)
    amount_made: int = Query(None)
    timestamp: int = Query(None)
    fullscreen_cam: int = Query(None)
    iframe_url: str = Query(None)
    success_url: str = Query(None)


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
