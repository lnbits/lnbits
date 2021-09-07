from . import db
from .models import Tip, TipJar

from ..satspay.crud import delete_charge  # type: ignore

import httpx

from http import HTTPStatus
from quart import jsonify

from typing import Optional

from lnbits.db import SQLITE
from lnbits.helpers import urlsafe_short_hash
from lnbits.core.crud import get_wallet


async def get_charge_details(tipjar_id):
    """Return the default details for a satspay charge"""
    details = {
        "time": 1440,
    }
    tipjar = await get_tipjar(tipjar_id)
    wallet_id = tipjar.wallet
    wallet = await get_wallet(wallet_id)
    user = wallet.user
    details["user"] = user
    details["lnbitswallet"] = wallet_id
    details["onchainwallet"] = tipjar.onchain
    return details


async def create_tip(
    id: str,
    wallet: str,
    sats: int,
    tipjar: int,
    name: str = "Anonymous",
    message: str = ""
) -> Tip:
    """Create a new Tip"""
    await db.execute(
        """
        INSERT INTO tipjar.Tips (
            id,
            wallet,
            name,
            message,
            sats,
            tipjar
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (id, wallet, name, message, sats, tipjar),
    )

    tip = await get_tip(id)
    assert tip, "Newly created tip couldn't be retrieved"
    return tip


async def create_tipjar(
    wallet: str,
    webhook: str,
    onchain: str = None,
) -> TipJar:
    """Create a new TipJar"""

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO tipjar.TipJars (
            wallet,
            webhook,
            onchain
        )
        VALUES (?, ?, ?)
        {returning}
        """,
        (
            wallet,
            webhook,
            onchain
        ),
    )
    if db.type == SQLITE:
        tipjar_id = result._result_proxy.lastrowid
    else:
        tipjar_id = result[0]

    tipjar = await get_tipjar(tipjar_id)
    assert tipjar
    return tipjar


async def get_tipjar(tipjar_id: int, by_state: str = None) -> Optional[TipJar]:
    """Return a tipjar by ID"""
    if by_state:
        row = await db.fetchone(
            "SELECT * FROM tipjar.TipJars WHERE state = ?", (by_state,)
        )
    else:
        row = await db.fetchone(
            "SELECT * FROM tipjar.TipJars WHERE id = ?", (tipjar_id,)
        )
    return TipJar.from_row(row) if row else None


async def get_tipjars(wallet_id: str) -> Optional[list]:
    """Return all TipJars belonging assigned to the wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM tipjar.TipJars WHERE wallet = ?", (wallet_id,)
    )
    return [TipJar.from_row(row) for row in rows] if rows else None


async def delete_tipjar(tipjar_id: int) -> None:
    """Delete a TipJar and all corresponding Tips"""
    await db.execute("DELETE FROM tipjar.TipJars WHERE id = ?", (tipjar_id,))
    rows = await db.fetchall(
        "SELECT * FROM tipjar.Tips WHERE tipjar = ?", (tipjar_id,)
    )
    for row in rows:
        await delete_tip(row["id"])


async def get_tip(tip_id: str) -> Optional[Tip]:
    """Return a Tip"""
    row = await db.fetchone(
        "SELECT * FROM tipjar.Tips WHERE id = ?", (tip_id,)
    )
    return Tip.from_row(row) if row else None


async def get_tips(wallet_id: str) -> Optional[list]:
    """Return all Tips assigned to wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM tipjar.Tips WHERE wallet = ?", (wallet_id,)
    )
    return [Tip.from_row(row) for row in rows] if rows else None


async def delete_tip(tip_id: str) -> None:
    """Delete a Tip and its corresponding statspay charge"""
    await db.execute("DELETE FROM tipjar.Tips WHERE id = ?", (tip_id,))
    await delete_charge(tip_id)


async def update_tip(tip_id: str, **kwargs) -> Tip:
    """Update a Tip"""
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE tipjar.Tips SET {q} WHERE id = ?",
        (*kwargs.values(), tip_id),
    )
    row = await db.fetchone(
        "SELECT * FROM tipjar.Tips WHERE id = ?", (tip_id,)
    )
    assert row, "Newly updated tip couldn't be retrieved"
    return Tip(**row)


async def update_tipjar(tipjar_id: str, **kwargs) -> TipJar:
    """Update a tipjar"""
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE tipjar.TipJars SET {q} WHERE id = ?",
        (*kwargs.values(), tipjar_id),
    )
    row = await db.fetchone(
        "SELECT * FROM tipjar.TipJars WHERE id = ?", (tipjar_id,)
    )
    assert row, "Newly updated tipjar couldn't be retrieved"
    return TipJar(**row)
