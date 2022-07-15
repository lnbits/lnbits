from fastapi.params import Query
from pydantic import BaseModel


class Card(BaseModel):
    id: str
    wallet: str
    card_name: str
    uid: str
    counter: int
    withdraw: str
    file_key: str
    meta_key: str
    time: int


class CreateCardData(BaseModel):
    card_name: str = Query(...)
    uid: str = Query(...)
    counter: str = Query(...)
    withdraw: str = Query(...)
    file_key: str = Query(...)
    meta_key: str = Query(...)


class Hit(BaseModel):
    id: str
    card_id: str
    ip: str
    useragent: str
    old_ctr: int
    new_ctr: int
    time: int
