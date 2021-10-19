from fastapi.param_functions import Query
from pydantic import BaseModel


class CreateEvent(BaseModel):
    wallet: str
    name: str
    info: str 
    closing_date: str 
    event_start_date: str 
    event_end_date: str
    amount_tickets: int = Query(..., ge=0)
    price_per_ticket: int = Query(..., ge=0)

class CreateTicket(BaseModel):
    name: str
    email: str

class Events(BaseModel):
    id: str
    wallet: str
    name: str
    info: str
    closing_date: str
    event_start_date: str
    event_end_date: str
    amount_tickets: int
    price_per_ticket: int
    sold: int
    time: int


class Tickets(BaseModel):
    id: str
    wallet: str
    event: str
    name: str
    email: str
    registered: bool
    paid: bool
    time: int
