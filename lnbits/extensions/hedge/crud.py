from typing import Optional

from lnbits.db import SQLITE

from ..satspay.crud import delete_charge  # type: ignore
from . import db
from .models import HedgedWallet, createHedgedWallet


async def create_hedge(data: createHedgedWallet) -> HedgedWallet:
    """Create a new HedgedWallet"""

    returning = "" if db.type == SQLITE else "RETURNING ID"
    method = db.execute if db.type == SQLITE else db.fetchone

    result = await (method)(
        f"""
        INSERT INTO hedge.HedgedWallets (
            ticker,
            wallet,
            hedgeuri,
            onchain
        )
        VALUES (?, ?, ?, ?)
        {returning}
        """,
        (data.ticker, data.wallet, data.hedgeuri, data.onchain),
    )
    if db.type == SQLITE:
        hedge_id = result._result_proxy.lastrowid
    else:
        hedge_id = result[0]

    hedge = await get_hedge(hedge_id)
    assert hedge
    return hedge


async def get_hedge(hedge_id: int) -> Optional[HedgedWallet]:
    """Return a hedge by ID"""
    row = await db.fetchone(
        "SELECT * FROM hedge.HedgedWallets WHERE id = ?", (hedge_id,)
    )
    return HedgedWallet(**row) if row else None


async def get_hedges(wallet_id: str) -> Optional[list]:
    """Return all HedgedWallets belonging assigned to the wallet_id"""
    rows = await db.fetchall(
        "SELECT * FROM hedge.HedgedWallets WHERE wallet = ?", (wallet_id,)
    )
    return [HedgedWallet(**row) for row in rows] if rows else None


async def delete_hedge(hedge_id: int) -> None:
    await db.execute("DELETE FROM hedge.HedgedWallets WHERE id = ?", (hedge_id,))


async def update_hedge(hedge_id: str, **kwargs) -> HedgedWallet:
    """Update a hedge"""
    q = ", ".join([f"{field[0]} = ?" for field in kwargs.items()])
    await db.execute(
        f"UPDATE hedge.HedgedWallets SET {q} WHERE id = ?", (*kwargs.values(), hedge_id)
    )
    row = await db.fetchone(
        "SELECT * FROM hedge.HedgedWallets WHERE id = ?", (hedge_id,)
    )
    assert row, "Newly updated hedge couldn't be retrieved"
    return HedgedWallet(**row)


async def get_all_hedges() -> Optional[list]:
    """Return all HedgedWallets belonging assigned to the wallet_id"""
    rows = await db.fetchall("SELECT * FROM hedge.HedgedWallets")
    return [HedgedWallet(**row) for row in rows] if rows else None
