from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Tickets, Forms
import httpx


async def create_ticket(
    payment_hash: str,
    wallet: str,
    form: str,
    name: str,
    email: str,
    ltext: str,
    sats: int,
) -> Tickets:
    await db.execute(
        """
        INSERT INTO lnticket.ticket (id, form, email, ltext, name, wallet, sats, paid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (payment_hash, form, email, ltext, name, wallet, sats, False),
    )

    ticket = await get_ticket(payment_hash)
    assert ticket, "Newly created ticket couldn't be retrieved"
    return ticket


async def set_ticket_paid(payment_hash: str) -> Tickets:
    row = await db.fetchone(
        "SELECT * FROM lnticket.ticket WHERE id = ?", (payment_hash,)
    )
    if row[7] == False:
        await db.execute(
            """
            UPDATE lnticket.ticket
            SET paid = true
            WHERE id = ?
            """,
            (payment_hash,),
        )

        formdata = await get_form(row[1])
        assert formdata, "Couldn't get form from paid ticket"

        amount = formdata.amountmade + row[7]
        await db.execute(
            """
            UPDATE lnticket.form2
            SET amountmade = ?
            WHERE id = ?
            """,
            (amount, row[1]),
        )

        ticket = await get_ticket(payment_hash)
        assert ticket, "Newly paid ticket could not be retrieved"

        if formdata.webhook:
            async with httpx.AsyncClient() as client:
                await client.post(
                    formdata.webhook,
                    json={
                        "form": ticket.form,
                        "name": ticket.name,
                        "email": ticket.email,
                        "content": ticket.ltext,
                    },
                    timeout=40,
                )
            return ticket

    ticket = await get_ticket(payment_hash)
    assert ticket, "Newly paid ticket could not be retrieved"
    return ticket


async def get_ticket(ticket_id: str) -> Optional[Tickets]:
    row = await db.fetchone("SELECT * FROM lnticket.ticket WHERE id = ?", (ticket_id,))
    return Tickets(**row) if row else None


async def get_tickets(wallet_ids: Union[str, List[str]]) -> List[Tickets]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnticket.ticket WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Tickets(**row) for row in rows]


async def delete_ticket(ticket_id: str) -> None:
    await db.execute("DELETE FROM lnticket.ticket WHERE id = ?", (ticket_id,))


# FORMS


async def create_form(
    *,
    wallet: str,
    name: str,
    webhook: Optional[str] = None,
    description: str,
    amount: int,
    flatrate: int,
) -> Forms:
    form_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO lnticket.form2 (id, wallet, name, webhook, description, flatrate, amount, amountmade)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (form_id, wallet, name, webhook, description, flatrate, amount, 0),
    )

    form = await get_form(form_id)
    assert form, "Newly created forms couldn't be retrieved"
    return form


async def update_form(form_id: str, **kwargs) -> Forms:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnticket.form2 SET {q} WHERE id = ?", (*kwargs.values(), form_id)
    )
    row = await db.fetchone("SELECT * FROM lnticket.form2 WHERE id = ?", (form_id,))
    assert row, "Newly updated form couldn't be retrieved"
    return Forms(**row)


async def get_form(form_id: str) -> Optional[Forms]:
    row = await db.fetchone("SELECT * FROM lnticket.form2 WHERE id = ?", (form_id,))
    return Forms(**row) if row else None


async def get_forms(wallet_ids: Union[str, List[str]]) -> List[Forms]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM lnticket.form2 WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Forms(**row) for row in rows]


async def delete_form(form_id: str) -> None:
    await db.execute("DELETE FROM lnticket.form2 WHERE id = ?", (form_id,))
