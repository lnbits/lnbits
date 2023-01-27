import hashlib
import json
from enum import Enum
from sqlite3 import Row
from typing import List, Optional

from pydantic import BaseModel, Field


class NostrRelay(BaseModel):
    id: str
    wallet: str
    name: str
    currency: str
    tip_options: Optional[str]
    tip_wallet: Optional[str]

    @classmethod
    def from_row(cls, row: Row) -> "NostrRelay":
        return cls(**dict(row))


class NostrEvent(BaseModel):
    id: str
    pubkey: str
    created_at: int
    kind: int
    tags: List[List[str]] = []
    content: str = ""
    sig: str

    def serialize(self) -> List:
        return [0, self.pubkey, self.created_at, self.kind, self.tags, self.content]

    def serialize_json(self) -> str:
        e = self.serialize()
        return json.dumps(e, separators=(",", ":"))

    @property
    def event_id(self) -> str:
        data = self.serialize_json()
        id = hashlib.sha256(data.encode()).hexdigest()
        return id

    def check_signature(self):
        event_id = self.event_id
        if self.id != event_id:
            raise ValueError(
                f"Invalid event id. Expected: '{event_id}' got '{self.id}'"
            )


class NostrFilter(BaseModel):
    ids: List[str] = []
    authors: List[str] = []
    kinds: List[int] = []
    e: List[str] = Field([], alias="#e")
    p: List[str] = Field([], alias="#p")
    since: Optional[int]
    until: Optional[int]
    limit: Optional[int]


class NostrEventType(str, Enum):
    EVENT = "EVENT"
    REQ = "REQ"
    CLOSE = "CLOSE"
