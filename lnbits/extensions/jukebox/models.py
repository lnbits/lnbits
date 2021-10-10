from typing import NamedTuple
from sqlite3 import Row
from fastapi.param_functions import Query


class CreateJukeLinkData(BaseModel):
    user: str = Query(None)
    title: str = Query(None)
    wallet: str = Query(None)
    sp_user: str = Query(None)
    sp_secret: str = Query(None)
    sp_access_token: str = Query(None)
    sp_refresh_token: str = Query(None)
    sp_device: str = Query(None)
    sp_playlists: str = Query(None)
    price: str = Query(None)


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
