from pydantic import BaseModel
from fastapi.params import Query

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