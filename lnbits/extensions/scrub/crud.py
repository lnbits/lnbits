from typing import List, Optional, Union

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateScrubLink, ScrubLink


async def create_scrub_link(data: CreateScrubLink) -> ScrubLink:
    scrub_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO scrub.scrub_links (
            id,
            wallet,
            description,
            payoraddress
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            scrub_id,
            data.wallet,
            data.description,
            data.payoraddress,
        ),
    )
    link = await get_scrub_link(scrub_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_scrub_link(link_id: str) -> Optional[ScrubLink]:
    row = await db.fetchone("SELECT * FROM scrub.scrub_links WHERE id = ?", (link_id,))
    return ScrubLink(**row) if row else None


async def get_scrub_links(wallet_ids: Union[str, List[str]]) -> List[ScrubLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM scrub.scrub_links WHERE wallet IN ({q})
        ORDER BY id
        """,
        (*wallet_ids,),
    )
    return [ScrubLink(**row) for row in rows]


async def update_scrub_link(link_id: int, **kwargs) -> Optional[ScrubLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE scrub.scrub_links SET {q} WHERE id = ?",
        (*kwargs.values(), link_id),
    )
    row = await db.fetchone("SELECT * FROM scrub.scrub_links WHERE id = ?", (link_id,))
    return ScrubLink(**row) if row else None


async def delete_scrub_link(link_id: int) -> None:
    await db.execute("DELETE FROM scrub.scrub_links WHERE id = ?", (link_id,))


async def get_scrub_by_wallet(wallet_id) -> Optional[ScrubLink]:
    row = await db.fetchone(
        "SELECT * from scrub.scrub_links WHERE wallet = ?",
        (wallet_id,),
    )
    return ScrubLink(**row) if row else None


async def unique_scrubed_wallet(wallet_id):
    (row,) = await db.fetchone(
        "SELECT COUNT(wallet) FROM scrub.scrub_links WHERE wallet = ?",
        (wallet_id,),
    )
    return row
