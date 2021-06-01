import json
import base64
import hashlib
from collections import OrderedDict
from quart import url_for
from typing import NamedTuple, Optional, List, Dict
from sqlite3 import Row


class Jukebox(NamedTuple):
    id: str
    user: str
    title: str
    wallet: str
    sp_user: str
    sp_secret: str
    sp_access_token: str
    sp_refresh_token: str
    sp_device: str
    sp_playlists: str
    price: int
    profit: int

    @classmethod
    def from_row(cls, row: Row) -> "Jukebox":
        return cls(**dict(row))

class JukeboxPayment(NamedTuple):
    payment_hash: str
    song_id: str
    paid: bool

    @classmethod
    def from_row(cls, row: Row) -> "JukeboxPayment":
        return cls(**dict(row))

class JukeboxQueue(NamedTuple):
    jukebox_id: str
    queue: str

    @classmethod
    def from_row(cls, row: Row) -> "JukeboxQueue":
        return cls(**dict(row))