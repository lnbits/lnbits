import secrets
from datetime import datetime
from typing import List, Optional

from lnbits.helpers import urlsafe_short_hash

from . import db
from .models import Card, CreateCardData, Hit, Refund


async def create_card(data: CreateCardData, wallet_id: str) -> Card:
    card_id = urlsafe_short_hash().upper()
    extenal_id = urlsafe_short_hash().lower()

    await db.execute(
        """
        INSERT INTO boltcards.cards (
            id,
            uid,
            external_id,
            wallet,
            card_name,
            counter,
            tx_limit,
            daily_limit,
            enable,
            k0,
            k1,
            k2,
            otp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            card_id,
            data.uid.upper(),
            extenal_id,
            wallet_id,
            data.card_name,
            data.counter,
            data.tx_limit,
            data.daily_limit,
            True,
            data.k0,
            data.k1,
            data.k2,
            secrets.token_hex(16),
        ),
    )
    card = await get_card(card_id)
    assert card, "Newly created card couldn't be retrieved"
    return card


async def update_card(card_id: str, **kwargs) -> Optional[Card]:
    if "is_unique" in kwargs:
        kwargs["is_unique"] = int(kwargs["is_unique"])
    if "uid" in kwargs:
        kwargs["uid"] = kwargs["uid"].upper()
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE boltcards.cards SET {q} WHERE id = ?",
        (*kwargs.values(), card_id),
    )
    row = await db.fetchone("SELECT * FROM boltcards.cards WHERE id = ?", (card_id,))
    return Card(**row) if row else None


async def get_cards(wallet_ids: List[str]) -> List[Card]:
    if len(wallet_ids) == 0:
        return []

    q = ",".join(["?"] * len(wallet_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltcards.cards WHERE wallet IN ({q})", (*wallet_ids,)
    )

    return [Card(**row) for row in rows]


async def get_card(card_id: str) -> Optional[Card]:
    row = await db.fetchone("SELECT * FROM boltcards.cards WHERE id = ?", (card_id,))
    if not row:
        return None

    card = dict(**row)

    return Card.parse_obj(card)


async def get_card_by_uid(card_uid: str) -> Optional[Card]:
    row = await db.fetchone(
        "SELECT * FROM boltcards.cards WHERE uid = ?", (card_uid.upper(),)
    )
    if not row:
        return None

    card = dict(**row)

    return Card.parse_obj(card)


async def get_card_by_external_id(external_id: str) -> Optional[Card]:
    row = await db.fetchone(
        "SELECT * FROM boltcards.cards WHERE external_id = ?", (external_id.lower(),)
    )
    if not row:
        return None

    card = dict(**row)

    return Card.parse_obj(card)


async def get_card_by_otp(otp: str) -> Optional[Card]:
    row = await db.fetchone("SELECT * FROM boltcards.cards WHERE otp = ?", (otp,))
    if not row:
        return None

    card = dict(**row)

    return Card.parse_obj(card)


async def delete_card(card_id: str) -> None:
    # Delete cards
    await db.execute("DELETE FROM boltcards.cards WHERE id = ?", (card_id,))
    # Delete hits
    hits = await get_hits([card_id])
    for hit in hits:
        await db.execute("DELETE FROM boltcards.hits WHERE id = ?", (hit.id,))
        # Delete refunds
        refunds = await get_refunds([hit.id])
        for refund in refunds:
            await db.execute(
                "DELETE FROM boltcards.refunds WHERE id = ?", (refund.hit_id,)
            )


async def update_card_counter(counter: int, id: str):
    await db.execute(
        "UPDATE boltcards.cards SET counter = ? WHERE id = ?",
        (counter, id),
    )


async def enable_disable_card(enable: bool, id: str) -> Optional[Card]:
    await db.execute(
        "UPDATE boltcards.cards SET enable = ? WHERE id = ?",
        (enable, id),
    )
    return await get_card(id)


async def update_card_otp(otp: str, id: str):
    await db.execute(
        "UPDATE boltcards.cards SET otp = ? WHERE id = ?",
        (otp, id),
    )


async def get_hit(hit_id: str) -> Optional[Hit]:
    row = await db.fetchone("SELECT * FROM boltcards.hits WHERE id = ?", (hit_id,))
    if not row:
        return None

    hit = dict(**row)

    return Hit.parse_obj(hit)


async def get_hits(cards_ids: List[str]) -> List[Hit]:
    if len(cards_ids) == 0:
        return []

    q = ",".join(["?"] * len(cards_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltcards.hits WHERE card_id IN ({q})", (*cards_ids,)
    )

    return [Hit(**row) for row in rows]


async def get_hits_today(card_id: str) -> List[Hit]:
    rows = await db.fetchall(
        "SELECT * FROM boltcards.hits WHERE card_id = ?",
        (card_id,),
    )
    updatedrow = []
    for row in rows:
        if datetime.now().date() == datetime.fromtimestamp(row.time).date():
            updatedrow.append(row)

    return [Hit(**row) for row in updatedrow]


async def spend_hit(id: str, amount: int):
    await db.execute(
        "UPDATE boltcards.hits SET spent = ?, amount = ? WHERE id = ?",
        (True, amount, id),
    )
    return await get_hit(id)


async def create_hit(card_id, ip, useragent, old_ctr, new_ctr) -> Hit:
    hit_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO boltcards.hits (
            id,
            card_id,
            ip,
            spent,
            useragent,
            old_ctr,
            new_ctr,
            amount
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            hit_id,
            card_id,
            ip,
            False,
            useragent,
            old_ctr,
            new_ctr,
            0,
        ),
    )
    hit = await get_hit(hit_id)
    assert hit, "Newly recorded hit couldn't be retrieved"
    return hit


async def create_refund(hit_id, refund_amount) -> Refund:
    refund_id = urlsafe_short_hash()
    await db.execute(
        """
        INSERT INTO boltcards.refunds (
            id,
            hit_id,
            refund_amount
        )
        VALUES (?, ?, ?)
        """,
        (
            refund_id,
            hit_id,
            refund_amount,
        ),
    )
    refund = await get_refund(refund_id)
    assert refund, "Newly recorded hit couldn't be retrieved"
    return refund


async def get_refund(refund_id: str) -> Optional[Refund]:
    row = await db.fetchone(
        "SELECT * FROM boltcards.refunds WHERE id = ?", (refund_id,)
    )
    if not row:
        return None
    refund = dict(**row)
    return Refund.parse_obj(refund)


async def get_refunds(hits_ids: List[str]) -> List[Refund]:
    if len(hits_ids) == 0:
        return []

    q = ",".join(["?"] * len(hits_ids))
    rows = await db.fetchall(
        f"SELECT * FROM boltcards.refunds WHERE hit_id IN ({q})", (*hits_ids,)
    )

    return [Refund(**row) for row in rows]
