from typing import List, Optional, Union

from . import db
from .models import PayLink


async def create_pay_link(
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
) -> PayLink:
    result = await db.execute(
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
    link_id = result._result_proxy.lastrowid
    link = await get_pay_link(link_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_pay_link(link_id: int) -> Optional[PayLink]:
    row = await db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def get_pay_links(wallet_ids: Union[str, List[str]]) -> List[PayLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM pay_links WHERE wallet IN ({q})
        ORDER BY Id
        """,
        (*wallet_ids,),
    )

    return [PayLink.from_row(row) for row in rows]


async def update_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id)
    )
    row = await db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def increment_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    q = ", ".join([f"{field[0]} = {field[0]} + ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id)
    )
    row = await db.fetchone("SELECT * FROM pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def delete_pay_link(link_id: int) -> None:
    await db.execute("DELETE FROM pay_links WHERE id = ?", (link_id,))
