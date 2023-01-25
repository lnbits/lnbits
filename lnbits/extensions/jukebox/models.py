from typing import Optional

from fastapi import Query
from pydantic import BaseModel


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


class Jukebox(BaseModel):
    id: str
    user: str
    title: str
    wallet: str
    inkey: Optional[str]
    sp_user: str
    sp_secret: str
    sp_access_token: Optional[str]
    sp_refresh_token: Optional[str]
    sp_device: Optional[str]
    sp_playlists: Optional[str]
    price: int
    profit: int


class JukeboxPayment(BaseModel):
    payment_hash: str
    juke_id: str
    song_id: str
    paid: bool


class CreateJukeboxPayment(BaseModel):
    invoice: str = Query(None)
    payment_hash: str = Query(None)
    juke_id: str = Query(None)
    song_id: str = Query(None)
    paid: bool = Query(False)
