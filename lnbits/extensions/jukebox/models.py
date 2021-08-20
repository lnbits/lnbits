from sqlite3 import Row
from pydantic import BaseModel


class Jukebox(BaseModel):
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


class JukeboxPayment(BaseModel):
    payment_hash: str
    juke_id: str
    song_id: str
    paid: bool

    @classmethod
    def from_row(cls, row: Row) -> "JukeboxPayment":
        return cls(**dict(row))
