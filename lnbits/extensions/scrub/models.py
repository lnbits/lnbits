import json
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, ParseResult
from starlette.requests import Request
from fastapi.param_functions import Query
from typing import Optional, Dict
from lnbits.lnurl import encode as lnurl_encode  # type: ignore
from sqlite3 import Row
from pydantic import BaseModel


class CreateScrubLink(BaseModel):
    wallet: str
    description: str
    payoraddress: str


class ScrubLink(BaseModel):
    id: int
    wallet: str
    description: str
    payoraddress: str

    @classmethod
    def from_row(cls, row: Row) -> "ScrubLink":
        data = dict(row)
        return cls(**data)

    def lnurl(self, req: Request) -> str:
        url = req.url_for("scrub.api_lnurl_response", link_id=self.id)
        return lnurl_encode(url)