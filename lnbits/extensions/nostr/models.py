import json
from sqlite3 import Row
from typing import Optional

from fastapi import Request
from lnurl import Lnurl
from lnurl import encode as lnurl_encode  # type: ignore
from lnurl.models import LnurlPaySuccessAction, UrlAction  # type: ignore
from lnurl.types import LnurlPayMetadata  # type: ignore
from pydantic import BaseModel
from pydantic.main import BaseModel

class nostrKeys(BaseModel):
    id: str
    pubkey: str
    privkey: str

class nostrNotes(BaseModel):
    id: str
    pubkey: str
    created_at: str
    kind: int
    tags: str
    content: str
    sig: str

class nostrRelays(BaseModel):
    id: str
    relay: str

class nostrConnections(BaseModel):
    id: str
    pubkey: str
    relayid: str