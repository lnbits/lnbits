from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.helpers import urlsafe_short_hash

from .models import Tickets, Forms




#######TICKETS########


def create_ticket(wallet: str, form: str,  name: str,  email: str, ltext: str, sats: int) -> Tickets:
    formdata = get_form(form)
    amount = formdata.amountmade + sats
    with open_ext_db("lnticket") as db:
        ticket_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO tickets (id, form, email, ltext, name, wallet, sats)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ticket_id, form, email, ltext, name, wallet, sats),
        )
        db.execute(
            """
            UPDATE forms
            SET amountmade = ?
            WHERE id = ?
            """,
            (amount, form),
        )
    return get_ticket(ticket_id)


def get_ticket(ticket_id: str) -> Optional[Tickets]:
    with open_ext_db("lnticket") as db:
        row = db.fetchone("SELECT * FROM tickets WHERE id = ?", (ticket_id,))

    return Tickets(**row) if row else None


def get_tickets(wallet_ids: Union[str, List[str]]) -> List[Tickets]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("lnticket") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM tickets WHERE wallet IN ({q})", (*wallet_ids,))

    return [Tickets(**row) for row in rows]


def delete_ticket(ticket_id: str) -> None:
    with open_ext_db("lnticket") as db:
        db.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))




########FORMS#########


def create_form(*, wallet: str, name: str, description: str, costpword: int) -> Forms:
    with open_ext_db("lnticket") as db:
        form_id = urlsafe_short_hash()
        db.execute(
            """
            INSERT INTO forms (id, wallet, name, description, costpword, amountmade)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (form_id, wallet, name, description, costpword, 0 ),
        )

    return get_form(form_id)

def update_form(form_id: str, **kwargs) -> Forms:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    with open_ext_db("lnticket") as db:
        db.execute(f"UPDATE forms SET {q} WHERE id = ?", (*kwargs.values(), form_id))
        row = db.fetchone("SELECT * FROM forms WHERE id = ?", (form_id,))

    return Forms(**row) if row else None


def get_form(form_id: str) -> Optional[Forms]:
    with open_ext_db("lnticket") as db:
        row = db.fetchone("SELECT * FROM forms WHERE id = ?", (form_id,))

    return Forms(**row) if row else None


def get_forms(wallet_ids: Union[str, List[str]]) -> List[Forms]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("lnticket") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM forms WHERE wallet IN ({q})", (*wallet_ids,))

    return [Forms(**row) for row in rows]


def delete_form(form_id: str) -> None:
    with open_ext_db("lnticket") as db:
        db.execute("DELETE FROM forms WHERE id = ?", (form_id,))