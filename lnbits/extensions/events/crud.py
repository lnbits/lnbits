from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Tickets, Events


# TICKETS


async def create_ticket(
    payment_hash: str, wallet: str, event: str, name: str, email: str
) -> Tickets:
    await db.execute(
        """
        INSERT INTO ticket (id, wallet, event, name, email, registered, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (payment_hash, wallet, event, name, email, False, False),
    )

    ticket = await get_ticket(payment_hash)
    assert ticket, "Newly created ticket couldn't be retrieved"
    return ticket


async def set_ticket_paid(payment_hash: str) -> Tickets:
    row = await db.fetchone("SELECT * FROM ticket WHERE id = ?", (payment_hash,))
    if row[6] != True:
        await db.execute(
            """
            UPDATE ticket
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )

        eventdata = await get_event(row[2])
        assert eventdata, "Couldn't get event from ticket being paid"

        sold = eventdata.sold + 1
        amount_tickets = eventdata.amount_tickets - 1
        await db.execute(
            """
            UPDATE events
            SET sold = ?, amount_tickets = ?
            WHERE id = ?
            """,
            (sold, amount_tickets, row[2]),
        )

    ticket = await get_ticket(payment_hash)
    assert ticket, "Newly updated ticket couldn't be retrieved"
    return ticket


async def get_ticket(payment_hash: str) -> Optional[Tickets]:
    row = await db.fetchone("SELECT * FROM ticket WHERE id = ?", (payment_hash,))
    return Tickets(**row) if row else None


async def get_tickets(wallet_ids: Union[str, List[str]]) -> List[Tickets]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM ticket WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [Tickets(**row) for row in rows]


async def delete_ticket(payment_hash: str) -> None:
    await db.execute("DELETE FROM ticket WHERE id = ?", (payment_hash,))


# EVENTS


async def create_event(
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
    event_id = urlsafe_short_hash()
    await db.execute(
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

    event = await get_event(event_id)
    assert event, "Newly created event couldn't be retrieved"
    return event


async def update_event(event_id: str, **kwargs) -> Events:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE events SET {q} WHERE id = ?", (*kwargs.values(), event_id)
    )
    event = await get_event(event_id)
    assert event, "Newly updated event couldn't be retrieved"
    return event


async def get_event(event_id: str) -> Optional[Events]:
    row = await db.fetchone("SELECT * FROM events WHERE id = ?", (event_id,))
    return Events(**row) if row else None


async def get_events(wallet_ids: Union[str, List[str]]) -> List[Events]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM events WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Events(**row) for row in rows]


async def delete_event(event_id: str) -> None:
    await db.execute("DELETE FROM events WHERE id = ?", (event_id,))


# EVENTTICKETS


async def get_event_tickets(event_id: str, wallet_id: str) -> List[Tickets]:
    rows = await db.fetchall(
        "SELECT * FROM ticket WHERE wallet = ? AND event = ?", (wallet_id, event_id)
    )
    return [Tickets(**row) for row in rows]


async def reg_ticket(ticket_id: str) -> List[Tickets]:
    await db.execute("UPDATE ticket SET registered = ? WHERE id = ?", (True, ticket_id))
    ticket = await db.fetchone("SELECT * FROM ticket WHERE id = ?", (ticket_id,))
    rows = await db.fetchall("SELECT * FROM ticket WHERE event = ?", (ticket[1],))
    return [Tickets(**row) for row in rows]
