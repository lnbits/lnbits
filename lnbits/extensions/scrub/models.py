from sqlite3 import Row

from pydantic import BaseModel
from starlette.requests import Request

from lnbits.lnurl import encode as lnurl_encode


class CreateScrubLink(BaseModel):
    wallet: str
    description: str
    payoraddress: str


class ScrubLink(BaseModel):
    id: str
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
