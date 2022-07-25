import json
from sqlite3 import Row
from typing import Dict, Optional
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse, urlunparse

from fastapi.param_functions import Query
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from starlette.requests import Request

from lnbits.lnurl import encode as lnurl_encode  # type: ignore


class CreateCopilotData(BaseModel):
    user: str = Query(None)
    title: str = Query(None)
    lnurl_toggle: int = Query(0)
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
    show_message: int = Query(0)
    show_ack: int = Query(0)
    show_price: str = Query(None)
    amount_made: int = Query(0)
    timestamp: int = Query(0)
    fullscreen_cam: int = Query(0)
    iframe_url: str = Query(None)
    success_url: str = Query(None)


class Copilots(BaseModel):
    id: str
    user: str = Query(None)
    title: str = Query(None)
    lnurl_toggle: int = Query(0)
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
    show_message: int = Query(0)
    show_ack: int = Query(0)
    show_price: str = Query(None)
    amount_made: int = Query(0)
    timestamp: int = Query(0)
    fullscreen_cam: int = Query(0)
    iframe_url: str = Query(None)
    success_url: str = Query(None)

    def lnurl(self, req: Request) -> str:
        url = req.url_for("copilot.lnurl_response", cp_id=self.id)
        return lnurl_encode(url)
