from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import Tickets, Events


#######TICKETS########


def create_ticket(payment_hash: str, wallet: str, event: str, name: str, email: str) -> Tickets:
    with open_ext_db("events") as db:
        db.execute(
            """
            INSERT INTO ticket (id, wallet, event, name, email, registered, paid)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (payment_hash, wallet, event, name, email, False, False),
        )

    return get_ticket(payment_hash)


def update_ticket(paid: bool, payment_hash: str) -> Tickets:
    with open_ext_db("events") as db:
        row = db.fetchone("SELECT * FROM ticket WHERE id = ?", (payment_hash,))
        if row[6] == True:
            return get_ticket(payment_hash)
        db.execute(
            """
            UPDATE ticket
            SET paid = ?
            WHERE id = ?
            """,
            (paid, payment_hash),
        )

        eventdata = get_event(row[2])
        sold = eventdata.sold + 1
        amount_tickets = eventdata.amount_tickets - 1
        db.execute(
            """
            UPDATE events
            SET sold = ?, amount_tickets = ?
            WHERE id = ?
            """,
            (sold, amount_tickets, row[2]),
        )
    return get_ticket(payment_hash)


def get_ticket(payment_hash: str) -> Optional[Tickets]:
    with open_ext_db("events") as db:
        row = db.fetchone("SELECT * FROM ticket WHERE id = ?", (payment_hash,))

    return Tickets(**row) if row else None


def get_tickets(wallet_ids: Union[str, List[str]]) -> List[Tickets]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("events") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM ticket WHERE wallet IN ({q})", (*wallet_ids,))
    print("scrum")
    return [Tickets(**row) for row in rows]


def delete_ticket(payment_hash: str) -> None:
    with open_ext_db("events") as db:
        db.execute("DELETE FROM ticket WHERE id = ?", (payment_hash,))


########EVENTS#########


def create_event(
    *,
    wallet: str,
    name: str,
    info: str,
    closing_date: str,
    event_start_date: str,
    event_end_date: str,
    amount_tickets: int,
    price_per_ticket: int,
) -> Events:
    with open_ext_db("events") as db:
        event_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO events (id, wallet, name, info, closing_date, event_start_date, event_end_date, amount_tickets, price_per_ticket, sold)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                wallet,
                name,
                info,
                closing_date,
                event_start_date,
                event_end_date,
                amount_tickets,
                price_per_ticket,
                0,
            ),
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
        rows = db.fetchall("SELECT * FROM ticket WHERE wallet = ? AND event = ?", (wallet_id, event_id))
        print(rows)

    return [Tickets(**row) for row in rows]


def reg_ticket(ticket_id: str) -> Tickets:
    with open_ext_db("events") as db:
        db.execute("UPDATE ticket SET registered = ? WHERE id = ?", (True, ticket_id))
        ticket = db.fetchone("SELECT * FROM ticket WHERE id = ?", (ticket_id,))
        print(ticket[1])
        rows = db.fetchall("SELECT * FROM ticket WHERE event = ?", (ticket[1],))

    return [Tickets(**row) for row in rows]
