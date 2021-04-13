from datetime import datetime
from typing import List, Optional, Union
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import WithdrawLink, HashCheck


async def create_withdraw_link(
    *,
    wallet_id: str,
    title: str,
    min_withdrawable: int,
    max_withdrawable: int,
    uses: int,
    wait_time: int,
    is_unique: bool,
    usescsv: str,
) -> WithdrawLink:
    link_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO withdraw_link (
            id,
            wallet,
            title,
            min_withdrawable,
            max_withdrawable,
            uses,
            wait_time,
            is_unique,
            unique_hash,
            k1,
            open_time,
            usescsv
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            link_id,
            wallet_id,
            title,
            min_withdrawable,
            max_withdrawable,
            uses,
            wait_time,
            int(is_unique),
            urlsafe_short_hash(),
            urlsafe_short_hash(),
            int(datetime.now().timestamp()) + wait_time,
            usescsv,
        ),
    )
    link = await get_withdraw_link(link_id, 0)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_withdraw_link(link_id: str, num=0) -> Optional[WithdrawLink]:
    row = await db.fetchone("SELECT * FROM withdraw_link WHERE id = ?", (link_id,))
    if not row:
        return None

    link = []
    for item in row:
        link.append(item)
    link.append(num)
    return WithdrawLink._make(link)


async def get_withdraw_link_by_hash(unique_hash: str, num=0) -> Optional[WithdrawLink]:
    row = await db.fetchone(
        "SELECT * FROM withdraw_link WHERE unique_hash = ?", (unique_hash,)
    )
    if not row:
        return None

    link = []
    for item in row:
        link.append(item)
    link.append(num)
    return WithdrawLink._make(link)


async def get_withdraw_links(wallet_ids: Union[str, List[str]]) -> List[WithdrawLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM withdraw_link WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [WithdrawLink.from_row(row) for row in rows]


async def update_withdraw_link(link_id: str, **kwargs) -> Optional[WithdrawLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE withdraw_link SET {q} WHERE id = ?", (*kwargs.values(), link_id)
    )
    row = await db.fetchone("SELECT * FROM withdraw_link WHERE id = ?", (link_id,))
    return WithdrawLink.from_row(row) if row else None


async def delete_withdraw_link(link_id: str) -> None:
    await db.execute("DELETE FROM withdraw_link WHERE id = ?", (link_id,))


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def create_hash_check(
    the_hash: str,
    lnurl_id: str,
) -> HashCheck:
    await db.execute(
        """
        INSERT INTO hash_check (
            id,
            lnurl_id
        )
        VALUES (?, ?)
        """,
        (
            the_hash,
            lnurl_id,
        ),
    )
    hashCheck = await get_hash_check(the_hash, lnurl_id)
    return hashCheck


async def get_hash_check(the_hash: str, lnurl_id: str) -> Optional[HashCheck]:
    rowid = await db.fetchone("SELECT * FROM hash_check WHERE id = ?", (the_hash,))
    rowlnurl = await db.fetchone(
        "SELECT * FROM hash_check WHERE lnurl_id = ?", (lnurl_id,)
    )
    if not rowlnurl:
        await create_hash_check(the_hash, lnurl_id)
        return {"lnurl": True, "hash": False}
    else:
        if not rowid:
            await create_hash_check(the_hash, lnurl_id)
            return {"lnurl": True, "hash": False}
        else:
            return {"lnurl": True, "hash": True}
