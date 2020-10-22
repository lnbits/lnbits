import json
from typing import List, Optional, Union

from lnbits.db import open_ext_db
from lnbits.core.models import Payment
from quart import g

from .models import PayLink


def create_pay_link(
    *,
    wallet_id: str,
    description: str,
    min: int,
    max: int,
    comment_chars: int = 0,
    currency: Optional[str] = None,
    webhook_url: Optional[str] = None,
    success_text: Optional[str] = None,
    success_url: Optional[str] = None,
) -> Optional[PayLink]:
    with open_ext_db("lnurlp") as db:
        db.execute(
            """
            INSERT INTO pay_links (
                wallet,
                description,
                min,
                max,
                served_meta,
                served_pr,
                webhook_url,
                success_text,
                success_url,
                comment_chars,
                currency
            )
            VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
            """,
            (
                wallet_id,
                description,
                min,
                max,
                webhook_url,
                success_text,
                success_url,
                comment_chars,
                currency,
            ),
        )
        link_id = db.cursor.lastrowid
    return get_pay_link(link_id)


def get_pay_link(link_id: int) -> Optional[PayLink]:
    with open_ext_db("lnurlp") as db:
        row = db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))

    return PayLink.from_row(row) if row else None


def get_pay_links(wallet_ids: Union[str, List[str]]) -> List[PayLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    with open_ext_db("lnurlp") as db:
        q = ",".join(["?"] * len(wallet_ids))
        rows = db.fetchall(
            f"""
            SELECT * FROM pay_links WHERE wallet IN ({q})
            ORDER BY Id
            """,
            (*wallet_ids,),
        )

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


def mark_webhook_sent(payment: Payment, status: int) -> None:
    payment.extra["wh_status"] = status
    g.db.execute(
        """
        UPDATE apipayments SET extra = ?
        WHERE hash = ?
        """,
        (json.dumps(payment.extra), payment.payment_hash),
    )
