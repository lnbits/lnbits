from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import Tickets, Events


#######TICKETS########


def create_ticket(wallet: str, event: str,  name: str,  email: str) -> Tickets:
    with open_ext_db("events") as db:
        eventdata = get_event(event)
        sold = eventdata.sold + 1
        amount_tickets = eventdata.amount_tickets - 1
        ticket_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO tickets (id, wallet, event, name, email, registered)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, wallet, event, name, email, False),
        )
        db.execute(
            """
            UPDATE events
            SET sold = ?, amount_tickets = ?
            WHERE id = ?
            """,
            (sold, amount_tickets, event),
        )
    return get_ticket(ticket_id)


def get_ticket(ticket_id: str) -> Optional[Tickets]:
    with open_ext_db("events") as db:
        row = db.fetchone("SELECT * FROM tickets WHERE id = ?", (ticket_id,))

    return Tickets(**row) if row else None


def get_tickets(wallet_ids: Union[str, List[str]]) -> List[Tickets]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("events") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM tickets WHERE wallet IN ({q})", (*wallet_ids,))
    print("scrum")
    return [Tickets(**row) for row in rows]


def delete_ticket(ticket_id: str) -> None:
    with open_ext_db("events") as db:
        db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))



########EVENTS#########


def create_event(*, wallet: str, name: str, info: str, closing_date: str, event_start_date: str, event_end_date: str, amount_tickets: int, price_per_ticket: int) -> Events:
    with open_ext_db("events") as db:
        event_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO events (id, wallet, name, info, closing_date, event_start_date, event_end_date, amount_tickets, price_per_ticket, sold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, wallet, name, info, closing_date, event_start_date, event_end_date, amount_tickets, price_per_ticket, 0),
        )
        print(event_id)

    return get_event(event_id)

def update_event(event_id: str, **kwargs) -> Events:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    with open_ext_db("events") as db:
        db.execute(f"UPDATE events SET {q} WHERE id = ?", (*kwargs.values(), event_id))
        row = db.fetchone("SELECT * FROM events WHERE id = ?", (event_id,))

    return Events(**row) if row else None


def get_event(event_id: str) -> Optional[Events]:
    with open_ext_db("events") as db:
        row = db.fetchone("SELECT * FROM events WHERE id = ?", (event_id,))

    return Events(**row) if row else None


def get_events(wallet_ids: Union[str, List[str]]) -> List[Events]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("events") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM events WHERE wallet IN ({q})", (*wallet_ids,))

    return [Events(**row) for row in rows]


def delete_event(event_id: str) -> None:
    with open_ext_db("events") as db:
        db.execute("DELETE FROM events WHERE id = ?", (event_id,))

########EVENTTICKETS#########

def get_event_tickets(event_id: str, wallet_id: str) -> Tickets:

    with open_ext_db("events") as db:
        rows = db.fetchall("SELECT * FROM tickets WHERE wallet = ? AND event = ?", (wallet_id, event_id))
        print(rows)

    return [Tickets(**row) for row in rows]