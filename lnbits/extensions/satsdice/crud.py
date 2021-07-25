from datetime import datetime
from typing import List, Optional, Union
from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import satsdiceWithdraw, HashCheck, satsdiceLink

##################FLIP LINKS

async def create_satsdice_pay(
    *,
    wallet_id: str,
    title: str,
    amount: int,
    success_text: Optional[str] = None,
    success_url: Optional[str] = None,
    odds: int = 0,
    current_odds: int = 0,
) -> satsdiceLink:
    result = await db.execute(
        """
        INSERT INTO satsdice.satsdice_pay (
            id,
            wallet,
            title,
            amount,
            served_meta,
            served_pr,
            success_text,
            success_url,
            odds,
            current_odds,
            open_time
        )
        VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            wallet_id,
            title,
            title,
            amount,
            success_text,
            success_url,
            odds,
            current_odds,
            int(datetime.now().timestamp()),
        ),
    )
    link_id = result._result_proxy.lastrowid
    link = await get_satsdice_pay(link_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_satsdice_pay(link_id: int) -> Optional[satsdiceLink]:
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_pay WHERE id = ?", (link_id,)
    )
    return satsdiceLink.from_row(row) if row else None


async def get_satsdice_pays(wallet_ids: Union[str, List[str]]) -> List[satsdiceLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM satsdice.satsdice_pay WHERE wallet IN ({q})
        ORDER BY Id
        """,
        (*wallet_ids,),
    )

    return [satsdiceLink.from_row(row) for row in rows]


async def update_satsdice_pay(link_id: int, **kwargs) -> Optional[satsdiceLink]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE satsdice.satsdice_pay SET {q} WHERE id = ?",
        (*kwargs.values(), link_id),
    )
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_pay WHERE id = ?", (link_id,)
    )
    return satsdiceLink.from_row(row) if row else None


async def increment_satsdice_pay(link_id: int, **kwargs) -> Optional[satsdiceLink]:
    q = ", ".join([f"{field[0]} = {field[0]} + ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE satsdice.satsdice_pay SET {q} WHERE id = ?",
        (*kwargs.values(), link_id),
    )
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_pay WHERE id = ?", (link_id,)
    )
    return satsdiceLink.from_row(row) if row else None


async def delete_satsdice_pay(link_id: int) -> None:
    await db.execute("DELETE FROM satsdice.satsdice_pay WHERE id = ?", (link_id,))


##################FLIP WITHDRAWS


async def create_satsdice_withdraw(
    *, satsdice_pay: str, title: str, value: int, used: int
) -> satsdiceWithdraw:
    await db.execute(
        """
        INSERT INTO satsdice.satsdice_withdraw (
            id,
            satsdice_pay,
            value,
            unique_hash,
            k1,
            open_time,
            used
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            urlsafe_short_hash(),
            satsdice_pay,
            value,
            urlsafe_short_hash(),
            urlsafe_short_hash(),
            int(datetime.now().timestamp()),
            used,
        ),
    )
    withdraw = await get_satsdice_withdraw(withdraw_id, 0)
    assert withdraw, "Newly created withdraw couldn't be retrieved"
    return withdraw


async def get_satsdice_withdraw(
    withdraw_id: str, num=0
) -> Optional[satsdiceWithdraw]:
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_withdraw WHERE id = ?", (withdraw_id,)
    )
    if not row:
        return None

    withdraw = []
    for item in row:
        withdraw.append(item)
    withdraw.append(num)
    return satsdiceWithdraw._make(withdraw)


async def get_satsdice_withdraw_by_hash(
    unique_hash: str, num=0
) -> Optional[satsdiceWithdraw]:
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_withdraw WHERE unique_hash = ?",
        (unique_hash,),
    )
    if not row:
        return None

    withdraw = []
    for item in row:
        withdraw.append(item)
    withdraw.append(num)
    return satsdiceWithdraw._make(withdraw)


async def get_satsdice_withdraws(
    wallet_ids: Union[str, List[str]]
) -> List[satsdiceWithdraw]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM satsdice.satsdice_withdraw WHERE wallet IN ({q})",
        (*wallet_ids,),
    )

    return [satsdiceWithdraw.from_row(row) for row in rows]


async def update_satsdice_withdraw(
    withdraw_id: str, **kwargs
) -> Optional[satsdiceWithdraw]:
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE satsdice.satsdice_withdraw SET {q} WHERE id = ?",
        (*kwargs.values(), withdraw_id),
    )
    row = await db.fetchone(
        "SELECT * FROM satsdice.satsdice_withdraw WHERE id = ?", (withdraw_id,)
    )
    return satsdiceWithdraw.from_row(row) if row else None


async def delete_satsdice_withdraw(withdraw_id: str) -> None:
    await db.execute(
        "DELETE FROM satsdice.satsdice_withdraw WHERE id = ?", (withdraw_id,)
    )


async def create_withdraw_hash_check(
    the_hash: str,
    lnurl_id: str,
) -> HashCheck:
    await db.execute(
        """
        INSERT INTO satsdice.hash_checkw (
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
    hashCheck = await get_withdraw_hash_checkw(the_hash, lnurl_id)
    return hashCheck


async def get_withdraw_hash_checkw(the_hash: str, lnurl_id: str) -> Optional[HashCheck]:
    rowid = await db.fetchone(
        "SELECT * FROM satsdice.hash_checkw WHERE id = ?", (the_hash,)
    )
    rowlnurl = await db.fetchone(
        "SELECT * FROM satsdice.hash_checkw WHERE lnurl_id = ?", (lnurl_id,)
    )
    if not rowlnurl:
        await create_withdraw_hash_check(the_hash, lnurl_id)
        return {"lnurl": True, "hash": False}
    else:
        if not rowid:
            await create_withdraw_hash_check(the_hash, lnurl_id)
            return {"lnurl": True, "hash": False}
        else:
            return {"lnurl": True, "hash": True}
