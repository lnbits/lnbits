import json
from sqlite3 import Row
from typing import Optional

from fastapi import Request
from pydantic import BaseModel
from pydantic.main import BaseModel


class nostrKeys(BaseModel):
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

class nostrCreateRelays(BaseModel):
    relay: str

class nostrCreateConnections(BaseModel):
    pubkey: str
    relayid: str

class nostrRelays(BaseModel):
    id: str
    relay: str

class nostrRelayList(BaseModel):
    id: str
    allowlist: str
    denylist: str

class nostrRelayDenyList(BaseModel):
    denylist: str

class nostrRelayAllowList(BaseModel):
    allowlist: str

class nostrConnections(BaseModel):
    id: str
    pubkey: str
    relayid: str
