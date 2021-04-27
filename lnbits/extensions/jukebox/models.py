import json
import base64
import hashlib
from collections import OrderedDict
from quart import url_for
from typing import NamedTuple, Optional, List, Dict

class Jukebox(NamedTuple):
    id: int
    wallet: str
    user: str
    secret: str
    token: str
    playlists: str

    @classmethod
    def from_row(cls, row: Row) -> "Charges":
        return cls(**dict(row))