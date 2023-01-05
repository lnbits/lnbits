from datetime import datetime
from typing import List, Optional, Union

import shortuuid

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import CreateWithdrawData, HashCheck, WithdrawLink


async def create_withdraw_link(
    data: CreateWithdrawData, wallet_id: str
) -> WithdrawLink:
    link_id = urlsafe_short_hash()[:6]
    available_links = ",".join([str(i) for i in range(data.uses)])
    await db.execute(
        """
        INSERT INTO withdraw.withdraw_link (
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
            usescsv,
            webhook_url,
            webhook_headers,
            webhook_body,
            custom_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            link_id,
            wallet_id,
            data.title,
            data.min_withdrawable,
            data.max_withdrawable,
            data.uses,
            data.wait_time,
            int(data.is_unique),
            urlsafe_short_hash(),
            urlsafe_short_hash(),
            int(datetime.now().timestamp()) + data.wait_time,
            available_links,
            data.webhook_url,
            data.webhook_headers,
            data.webhook_body,
            data.custom_url,
        ),
    )
    link = await get_withdraw_link(link_id, 0)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_withdraw_link(link_id: str, num=0) -> Optional[WithdrawLink]:
    row = await db.fetchone(
        "SELECT * FROM withdraw.withdraw_link WHERE id = ?", (link_id,)
    )
    if not row:
        return None

    link = dict(**row)
    link["number"] = num

    return WithdrawLink.parse_obj(link)


async def get_withdraw_link_by_hash(unique_hash: str, num=0) -> Optional[WithdrawLink]:
    row = await db.fetchone(
        "SELECT * FROM withdraw.withdraw_link WHERE unique_hash = ?", (unique_hash,)
    )
    if not row:
        return None

    link = dict(**row)
    link["number"] = num

    return WithdrawLink.parse_obj(link)


async def get_withdraw_links(wallet_ids: Union[str, List[str]]) -> List[WithdrawLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM withdraw.withdraw_link WHERE wallet IN ({q})", (*wallet_ids,)
    )
    return [WithdrawLink(**row) for row in rows]


async def remove_unique_withdraw_link(link: WithdrawLink, unique_hash: str) -> None:
    unique_links = [
        x.strip()
        for x in link.usescsv.split(",")
        if unique_hash != shortuuid.uuid(name=link.id + link.unique_hash + x.strip())
    ]
    await update_withdraw_link(
        link.id,
        usescsv=",".join(unique_links),
    )


async def increment_withdraw_link(link: WithdrawLink) -> None:
    await update_withdraw_link(
        link.id,
        used=link.used + 1,
        open_time=link.wait_time + int(datetime.now().timestamp()),
    )


async def update_withdraw_link(link_id: str, **kwargs) -> Optional[WithdrawLink]:
    if "is_unique" in kwargs:
        kwargs["is_unique"] = int(kwargs["is_unique"])
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE withdraw.withdraw_link SET {q} WHERE id = ?",
        (*kwargs.values(), link_id),
    )
    row = await db.fetchone(
        "SELECT * FROM withdraw.withdraw_link WHERE id = ?", (link_id,)
    )
    return WithdrawLink(**row) if row else None


async def delete_withdraw_link(link_id: str) -> None:
    await db.execute("DELETE FROM withdraw.withdraw_link WHERE id = ?", (link_id,))


def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def create_hash_check(the_hash: str, lnurl_id: str) -> HashCheck:
    await db.execute(
        """
        INSERT INTO withdraw.hash_check (
            id,
            lnurl_id
        )
        VALUES (?, ?)
        """,
        (the_hash, lnurl_id),
    )
    hashCheck = await get_hash_check(the_hash, lnurl_id)
    return hashCheck


async def get_hash_check(the_hash: str, lnurl_id: str) -> HashCheck:
    rowid = await db.fetchone(
        "SELECT * FROM withdraw.hash_check WHERE id = ?", (the_hash,)
    )
    rowlnurl = await db.fetchone(
        "SELECT * FROM withdraw.hash_check WHERE lnurl_id = ?", (lnurl_id,)
    )
    if not rowlnurl:
        await create_hash_check(the_hash, lnurl_id)
        return HashCheck(lnurl=True, hash=False)
    else:
        if not rowid:
            await create_hash_check(the_hash, lnurl_id)
            return HashCheck(lnurl=True, hash=False)
        else:
            return HashCheck(lnurl=True, hash=True)
