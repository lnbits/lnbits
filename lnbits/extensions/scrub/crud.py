from typing import List, Optional, Union

from lnbits.db import SQLITE
from . import db
from .models import ScrubLink, CreateScrubLinkData


async def create_scrub_link(wallet_id: str, data: CreateSatsDiceLink) -> satsdiceLink:
    satsdice_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO scrub.scrub_links (
            id,
            wallet,
            description,
            payoraddress,
        )
        VALUES (?, ?, ?)
        """,
        (
            satsdice_id,
            wallet,
            description,
            payoraddress,
        ),
    )
    link = await get_satsdice_pay(satsdice_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_scrub_link(link_id: str) -> Optional[satsdiceLink]:
    row = await db.fetchone(
        "SELECT * FROM scrub.scrub_links WHERE id = ?", (link_id,)
    )
    return satsdiceLink(**row) if row else None


async def get_scrub_links(wallet_ids: Union[str, List[str]]) -> List[satsdiceLink]:
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
    return [satsdiceLink(**row) for row in rows]


async def update_scrub_link(link_id: int, **kwargs) -> Optional[satsdiceLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE scrub.scrub_links SET {q} WHERE id = ?",
        (*kwargs.values(), link_id),
    )
    row = await db.fetchone(
        "SELECT * FROM scrub.scrub_links WHERE id = ?", (link_id,)
    )
    return satsdiceLink(**row) if row else None

async def delete_scrub_link(link_id: int) -> None:
    await db.execute("DELETE FROM scrub.scrub_links WHERE id = ?", (link_id,))
