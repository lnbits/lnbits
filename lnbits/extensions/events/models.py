from typing import NamedTuple


class Events(NamedTuple):
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

class Tickets(NamedTuple):
    id: str
    wallet: str
    event: str
    name: str
    email: str
    registered: bool
    time: int