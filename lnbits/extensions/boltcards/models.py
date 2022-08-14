from fastapi.params import Query
from pydantic import BaseModel

ZERO_KEY = "00000000000000000000000000000000"


class Card(BaseModel):
    id: str
    wallet: str
    card_name: str
    uid: str
    counter: int
    withdraw: str
    k0: str
    k1: str
    k2: str
    prev_k0: str
    prev_k1: str
    prev_k2: str
    otp: str
    time: int


class CreateCardData(BaseModel):
    card_name: str = Query(...)
    uid: str = Query(...)
    counter: int = Query(0)
    withdraw: str = Query(...)
    k0: str = Query(ZERO_KEY)
    k1: str = Query(ZERO_KEY)
    k2: str = Query(ZERO_KEY)
    prev_k0: str = Query(ZERO_KEY)
    prev_k1: str = Query(ZERO_KEY)
    prev_k2: str = Query(ZERO_KEY)


class Hit(BaseModel):
    id: str
    card_id: str
    ip: str
    useragent: str
    old_ctr: int
    new_ctr: int
    time: int
