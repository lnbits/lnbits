from typing import List, Optional, Union

from lnbits import bolt11
from lnbits.db import open_ext_db

from .models import PayLink


def create_pay_link(
    *, wallet_id: str, description: str, amount: int, webhook_url: Optional[str] = None
) -> Optional[PayLink]:
    with open_ext_db("lnurlp") as db:
        db.execute(
            """
            INSERT INTO pay_links (
                wallet,
                description,
                amount,
                served_meta,
                served_pr,
                webhook_url
            )
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (wallet_id, description, amount, webhook_url),
        )
        link_id = db.cursor.lastrowid
    return get_pay_link(link_id)


def get_pay_link(link_id: int) -> Optional[PayLink]:
    with open_ext_db("lnurlp") as db:
        row = db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))

    return PayLink.from_row(row) if row else None


def get_pay_link_by_invoice(payment_hash: str) -> Optional[PayLink]:
    # this excludes invoices with webhooks that have been sent already

    with open_ext_db("lnurlp") as db:
        row = db.fetchone(
            """
            SELECT pay_links.* FROM pay_links
            INNER JOIN invoices ON invoices.pay_link = pay_links.id
            WHERE payment_hash = ? AND webhook_sent IS NULL
            """,
            (payment_hash,),
        )

    return PayLink.from_row(row) if row else None


def get_pay_links(wallet_ids: Union[str, List[str]]) -> List[PayLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("lnurlp") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(f"SELECT * FROM pay_links WHERE wallet IN ({q})", (*wallet_ids,))

    return [PayLink.from_row(row) for row in rows]


def update_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    with open_ext_db("lnurlp") as db:
        db.execute(f"UPDATE pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id))
        row = db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))

    return PayLink.from_row(row) if row else None


def increment_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    q = ", ".join([f"{field[0]} = {field[0]} + ?" for field in kwargs.items()])

    with open_ext_db("lnurlp") as db:
        db.execute(f"UPDATE pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id))
        row = db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))

    return PayLink.from_row(row) if row else None


def delete_pay_link(link_id: int) -> None:
    with open_ext_db("lnurlp") as db:
        db.execute("DELETE FROM pay_links WHERE id = ?", (link_id,))


def save_link_invoice(link_id: int, payment_request: str) -> None:
    inv = bolt11.decode(payment_request)

    with open_ext_db("lnurlp") as db:
        db.execute(
            """
            INSERT INTO invoices (pay_link, payment_hash, expiry)
            VALUES (?, ?, ?)
            """,
            (link_id, inv.payment_hash, inv.expiry),
        )


def mark_webhook_sent(payment_hash: str, status: int) -> None:
    with open_ext_db("lnurlp") as db:
        db.execute(
            """
            UPDATE invoices SET webhook_sent = ?
            WHERE payment_hash = ?
            """,
            (status, payment_hash),
        )
