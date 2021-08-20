from pydantic import BaseModel

class Forms(BaseModel):
    id: str
    wallet: str
    name: str
    webhook: str
    description: str
    amount: int
    flatrate: int
    amountmade: int
    time: int


class Tickets(BaseModel):
    id: str
    form: str
    email: str
    ltext: str
    name: str
    wallet: str
    sats: int
    paid: bool
    time: int
