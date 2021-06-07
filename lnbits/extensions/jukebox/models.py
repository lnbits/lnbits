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
    inkey: str
    sp_user: str
    sp_secret: str
    sp_access_token: str
    sp_refresh_token: str
    sp_device: str
    sp_playlists: str
    price: int
    profit: int
    queue: list
    last_checked: int

    @classmethod
    def from_row(cls, row: Row) -> "Jukebox":
        return cls(**dict(row))


class JukeboxPayment(NamedTuple):
    payment_hash: str
    juke_id: str
    song_id: str
    paid: bool

    @classmethod
    def from_row(cls, row: Row) -> "JukeboxPayment":
        return cls(**dict(row))
