from fastapi.param_functions import Query
from pydantic import BaseModel
from pydantic.main import BaseModel


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
    inkey: str
    sp_user: str
    sp_secret: str
    sp_access_token: str
    sp_refresh_token: str
    sp_device: str
    sp_playlists: str
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
