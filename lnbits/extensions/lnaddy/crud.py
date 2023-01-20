import re
from typing import List, Optional, Union

from loguru import logger

from lnbits.db import SQLITE

from . import db, maindb
from .models import CreatePayLinkData, PayLink


async def check_lnaddress_update(lnaddress: str, id: str) -> bool:
    # check no duplicates for lnaddress when updating an lnaddress name
    row = await db.fetchall(
        "SELECT lnaddress FROM lnaddy.pay_links WHERE lnaddress = ? AND id = ?",
        (lnaddress, id),
    )
    logger.info("number of rows from lnaddress search")
    logger.info(len(row))
    if len(row) > 1:
        assert False, "Lighting Address Already exists. Try a different One?"
        return
    else:
        return True


async def check_lnaddress_exists(lnaddress: str) -> bool:
    # check if lnaddress name exists in the database when creating a new entry
    row = await db.fetchall(
        "SELECT lnaddress FROM lnaddy.pay_links WHERE lnaddress = ?", (lnaddress,)
    )
    logger.info("number of rows from lnaddress search")
    if row:
        assert False, "Lighting Address Already exists. Try a different One?"
        return
    else:
        return True


async def check_lnaddress_format(lnaddress: str) -> bool:
    if not re.match("^[a-z0-9-_.]{3,15}$", lnaddress):
        assert False, "Only letters a-z0-9-_. allowed, min 3 and max 15 characters!"
        return
    return True


async def get_wallet_key(wallet_id: str) -> str:
    row = await maindb.fetchone("SELECT inkey FROM wallets WHERE id = ?", (wallet_id,))
    if row is not None:
        return row[0]
    else:
        assert False, "Cannot locate wallet invoice key"
        return


async def create_pay_link(data: CreatePayLinkData, wallet_id: str) -> PayLink:
    await check_lnaddress_format(data.lnaddress)
    await check_lnaddress_exists(data.lnaddress)
    wallet_key = await get_wallet_key(wallet_id)

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO lnaddy.pay_links (
            wallet,
            wallet_key,
            description,
            min,
            max,
            served_meta,
            served_pr,
            webhook_url,
            webhook_headers,
            webhook_body,
            success_text,
            success_url,
            comment_chars,
            currency,
            fiat_base_multiplier,
            lnaddress
        )
        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        {returning}
        """,
        (
            wallet_id,
            wallet_key,
            data.description,
            data.min,
            data.max,
            data.webhook_url,
            data.webhook_headers,
            data.webhook_body,
            data.success_text,
            data.success_url,
            data.comment_chars,
            data.currency,
            data.fiat_base_multiplier,
            data.lnaddress,
        ),
    )
    if db.type == SQLITE:
        link_id = result._result_proxy.lastrowid
    else:
        link_id = result[0]

    link = await get_pay_link(link_id)
    assert link, "Newly created link couldn't be retrieved"
    return link


async def get_address_data(lnaddress: str) -> Optional[PayLink]:
    row = await db.fetchone(
        "SELECT * FROM lnaddy.pay_links WHERE lnaddress = ?", (lnaddress,)
    )
    return PayLink.from_row(row) if row else None


async def get_pay_link(link_id: int) -> Optional[PayLink]:
    row = await db.fetchone("SELECT * FROM lnaddy.pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def get_pay_links(wallet_ids: Union[str, List[str]]) -> List[PayLink]:
    if isinstance(wallet_ids, str):
        wallet_ids = [wallet_ids]

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"""
        SELECT * FROM lnaddy.pay_links WHERE wallet IN ({q})
        ORDER BY Id
        """,
        (*wallet_ids,),
    )
    return [PayLink.from_row(row) for row in rows]


async def update_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    for field in kwargs.items():
        if field[0] == "lnaddress":
            value = field[1]
            logger.info(value)
            await check_lnaddress_format(value)
            await check_lnaddress_update(value, str(link_id))

    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])

    await db.execute(
        f"UPDATE lnaddy.pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id)
    )
    row = await db.fetchone("SELECT * FROM lnaddy.pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def increment_pay_link(link_id: int, **kwargs) -> Optional[PayLink]:
    q = ", ".join([f"{field[0]} = {field[0]} + ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE lnaddy.pay_links SET {q} WHERE id = ?", (*kwargs.values(), link_id)
    )
    row = await db.fetchone("SELECT * FROM lnaddy.pay_links WHERE id = ?", (link_id,))
    return PayLink.from_row(row) if row else None


async def delete_pay_link(link_id: int) -> None:
    await db.execute("DELETE FROM lnaddy.pay_links WHERE id = ?", (link_id,))
